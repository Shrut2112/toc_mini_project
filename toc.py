from typing import List

PLACEHOLDER = "\x07"  # BEL char used as temporary placeholder for semicolons inside for headers

class TMFormatter:
    def __init__(self, input_text: str, blank: str = "▢", indent_str: str = "    "):
        self.tape: List[str] = list(input_text)
        self.blank = blank
        self.tape.append(self.blank)
        self.head = 0
        self.indent_str = indent_str
        self.log_enabled = False
        self.step_count = 0

    def read(self) -> str:
        if self.head >= len(self.tape):
            return self.blank
        return self.tape[self.head]

    def write(self, ch: str):
        if self.head >= len(self.tape):
            while len(self.tape) <= self.head:
                self.tape.append(self.blank)
        self._log(f"WRITE '{ch}' at {self.head} (was '{self.tape[self.head]}')")
        self.tape[self.head] = ch

    def move_right(self):
        self._log(f"MOVE R {self.head} -> {self.head+1}")
        self.head += 1
        if self.head >= len(self.tape):
            self.tape.append(self.blank)

    def move_left(self):
        new = max(0, self.head - 1)
        self._log(f"MOVE L {self.head} -> {new}")
        self.head = new

    def insert(self, ch: str):
        self._log(f"INSERT '{ch}' at {self.head}")
        if self.head >= len(self.tape):
            self.tape.append(ch)
        else:
            self.tape.insert(self.head, ch)

    def delete(self):
        if self.head < len(self.tape):
            self._log(f"DELETE '{self.tape[self.head]}' at {self.head}")
            del self.tape[self.head]
            if len(self.tape) == 0:
                self.tape.append(self.blank)
        else:
            self._log("DELETE noop at blank")

    def _log(self, msg: str):
        self.step_count += 1
        if self.log_enabled:
            print(f"[{self.step_count:05d}] {msg}")

    def tape_str(self) -> str:
        s = "".join(self.tape)
        if self.blank != "":
            s = s.rstrip(self.blank)
        return s
    
    def _peek_right(self, offset=1):
        # Save original head position
        original_head = self.head
        
        # Move right offset times
        for _ in range(offset):
            self.move_right()
        
        # Read the symbol at that position
        symbol = self.read()
        
        # Move back to original position
        while self.head > original_head:
            self.move_left()
        
        return symbol


    def pass_normalize_whitespace(self):
        self._log("=== PASS: normalize whitespace ===")
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break
            if ch in (" ", "\t"):
                self.move_right()
                while self.read() in (" ", "\t"):
                    self.delete()
            else:
                self.move_right()

    def pass_protect_for_headers(self):
        self._log("=== PASS: protect for(...) semicolons ===")
        self.head = 0

        while True:
            ch = self.read()
            if ch == self.blank:
                break

            if ch == 'f':
                pos_f = self.head  

                self.move_right()
                ch1 = self.read()
                if ch1 != 'o':
                    self.head = pos_f
                    self.move_right()
                    continue

                self.move_right()
                ch2 = self.read()
                if ch2 != 'r':
                    self.head = pos_f
                    self.move_right()
                    continue

                if pos_f > 0:
                    self.head = pos_f - 1
                    prev = self.read()
                    if prev.isalnum() or prev == '_':
                        self.head = pos_f
                        self.move_right()
                        continue

                self.head = pos_f + 3 

                while self.read() in (" ", "\t"):
                    self.move_right()

                if self.read() != '(':
                    self.move_right()
                    continue

                stack = 0

                while True:
                    c = self.read()

                    if c == self.blank:
                        break

                    if c == '(':
                        stack += 1
                    elif c == ')':
                        stack -= 1
                        if stack == 0:
                            break
                    elif c == ';' and stack > 0:
                        self.write(PLACEHOLDER)

                    self.move_right()

                self.move_right()
                continue

            self.move_right()


    def pass_space_around_operators(self):
        self._log("=== PASS: space around operators ===")

        ops_single = set("=+-*/%<>!&|,^")
        multi_ops = {"==", "!=", "<=", ">=", "&&", "||", "+=", "-=", "*=", "/=", "++", "--", "::", "->"}

        self.head = 0

        while True:
            ch = self.read()
            if ch == self.blank:
                break

            pos = self.head  

            self.move_right()
            ch2 = self.read()

            self.move_left()

            two = ch + ch2

            if two in multi_ops:

                self._ensure_space_before()

                self.move_right()  
                self.move_right()  

                self._ensure_space_after()
                continue

            if ch in ops_single:
                self._ensure_space_before()

                self.move_right()

                self._ensure_space_after()
                continue

            self.move_right()


    def _ensure_space_before(self):
        if self.head == 0:
            return
        self.move_left()
        if self.read() == "\n":
            self.move_right()
            return
        if self.read() == " ":
            while self.head > 0 and self.read() == " " and (self.head - 1 >= 0 and self.tape[self.head - 1] == " "):
                self.delete()
            self.move_right()
            return
        else:
            self.insert(" ")
            self.move_right()
            return

    def _ensure_space_after(self):
        ch = self.read()
        if ch == "\n" or ch == self.blank:
            return
        if ch == " ":
            while self._peek_right() == " ":
                saved = self.head
                self.move_right()
                self.delete()
                self.head = saved
            return
        else:
            self.insert(" ")
            self.move_right()
            return

    def pass_autobrace_single_statements(self):
        
        self._log("=== PASS: auto-insert braces for single statements ===")
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break

            if ch in ('i', 'f', 'w'):
                token = None
                if ch == 'i' and self._peek_right() == 'f':
                    token = 'if'
                    token_len = 2
                elif ch == 'f' and self._peek_right() == 'o' and self._peek_right(2) == 'r':
                    token = 'for'
                    token_len = 3
                elif ch == 'w' and ''.join(self._peek_right(i) for i in range(1,5))[:4] == 'hile':
                    token = 'while'
                    token_len = 5

                if token:
                    prev_ok = True
                    if self.head - 1 >= 0:
                        prev = self.tape[self.head - 1]
                        if prev.isalnum() or prev == '_':
                            prev_ok = False

                    if not prev_ok:
                        self.move_right()
                        continue

                    for _ in range(token_len - 1):
                        self.move_right()
                    self.move_right()  
                    
                    while self.read() in (" ", "\t"):
                        self.move_right()
                    
                    if self.read() == '(':
                        
                        stack = 0
                        while True:
                            if self.read() == '(':
                                stack += 1
                            elif self.read() == ')':
                                stack -= 1
                                if stack == 0:
                                    break
                            self.move_right()
                            if self.read() == self.blank:
                                break
                        
                        self.move_right()
                        
                        while self.read() in (" ", "\t", "\n"):
                            
                            self.move_right()
                        
                        if self.read() == '{':  
                            continue
                        
                        insert_pos = self.head
                        self.insert('{')
                        
                        self.move_right()
                        
                        paren = 0
                        brace = 0
                        saw_anything = False
                        while True:
                            c = self.read()
                            if c == self.blank:
                                
                                while self.read() != self.blank:
                                    self.move_right()
                                self.insert('}')
                                self.move_right()
                                break

                            saw_anything = True
                            if c == '(':
                                paren += 1
                            elif c == ')':
                                if paren > 0:
                                    paren -= 1
                            elif c == '{':
                                brace += 1
                            elif c == '}':
                                if brace > 0:
                                    brace -= 1
                           
                            if c == ';' and paren == 0 and brace == 0:
                                
                                self.move_right()
                                
                                self.insert('}')
                                self.move_right()
                                break
                            
                            self.move_right()
                        continue
            if ch == 'e' and self._peek_right() == 'l' and self._peek_right(2) == 's' and self._peek_right(3) == 'e':
                
                start = self.head
                self.move_right(); self.move_right(); self.move_right(); self.move_right()
                
                while self.read() in (" ", "\t"):
                    self.move_right()
                
                if self.read() == 'i' and self._peek_right() == 'f':
                    
                    self.head = start + 1
                    continue
                
                if self.read() == '{':
                    
                    self.head = start + 1
                    continue
                else:
                   
                    insert_pos = self.head
                    self.insert('{')
                    self.move_right()
                    
                    paren = 0; brace = 0
                    while True:
                        c = self.read()
                        if c == self.blank:
                            
                            while self.read() != self.blank:
                                self.move_right()
                            self.insert('}')
                            self.move_right()
                            break
                        if c == '(':
                            paren += 1
                        elif c == ')':
                            if paren > 0:
                                paren -= 1
                        elif c == '{':
                            brace += 1
                        elif c == '}':
                            if brace > 0:
                                brace -= 1
                        if c == ';' and paren == 0 and brace == 0:
                            self.move_right()
                            self.insert('}')
                            self.move_right()
                            break
                        self.move_right()
                    
                    continue

            self.move_right()

    def pass_semicolon_newlines(self):
        self._log("=== PASS: semicolon newlines (ignoring placeholders) ===")
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break
            if ch == ';':
                
                self.move_right()
                if self.read() != '\n':
                    self.insert('\n')
                continue
            
            if ch == PLACEHOLDER:
                
                self.move_right()
                continue
            self.move_right()

    def pass_restore_placeholders(self):
        self._log("=== PASS: restore placeholders ===")
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break
            if ch == PLACEHOLDER:
                self.write(';')
            self.move_right()

    def pass_braces_newlines(self):
        self._log("=== PASS: braces on their own lines ===")
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break
            if ch == '{' or ch == '}':
                
                if self.head == 0:
                    self.insert('\n')
                    self.move_right()
                else:
                   
                    self.move_left()
                    while self.read() in (' ', '\t'):
                        self.move_left()
                    if self.read() != '\n':
                        
                        self.move_right()
                        self.insert('\n')
                        self.move_right()
                    else:
                       
                        while self.read() not in ('{', '}') and self.read() != self.blank:
                            self.move_right()
               
                self.move_right()
                if self.read() != '\n':
                    self.insert('\n')
                continue
            self.move_right()

    def pass_trim_blank_lines(self):
        self._log("=== PASS: trim blank lines & edges ===")
     
        self.head = 0
        while True:
            ch = self.read()
            if ch == self.blank:
                break
            if ch == '\n':
                self.move_right()
                while self.read() == '\n':
                    self.delete()
                continue
            self.move_right()
       
        self.head = 0
        while self.read() in (' ', '\t', '\n'):
            self.delete()
       
        while self.read() != self.blank:
            self.move_right()
        if self.head > 0:
            self.move_left()
            while self.read() in (' ', '\t', '\n'):
                self.delete()
                if self.head == 0:
                    break
                else:
                    self.move_left()

    def pass_indentation(self):
        self._log("=== PASS: indentation ===")
        indent_level = 0
        self.head = 0

        if self.read() != '\n':
            self.insert('\n')
            self.move_right()
        while True:
            c = self.read()
            if c == self.blank:
                break
            if c == '\n':
                
                self.move_right()
                if self.read() == self.blank:
                    break

                line_start = self.head
                
                while self.read() in (' ', '\t'):
                    self.delete()
               
                saved = self.head
                
                while self.read() in (' ', '\t'):
                    self.move_right()
                first = self.read()
               
                if first == '}':
                    indent_level = max(0, indent_level - 1)
                
                self.head = line_start
                for _ in range(indent_level):
                    for ch in self.indent_str:
                        self.insert(ch)
                        self.move_right()
             
                self.head = saved + indent_level * len(self.indent_str)
    
                saw_open = False
                while self.read() not in ('\n', self.blank):
                    if self.read() == '{':
                        saw_open = True
                    self.move_right()
                if saw_open:
                    indent_level += 1
                continue
            else:
                self.move_right()

        if self.tape and self.tape[0] == '\n':
            self.head = 0
            self.delete()


    def format(self, verbose: bool = True) -> str:
        self.log_enabled = verbose

        self.pass_normalize_whitespace()
        self._snapshot("After normalize")

        self.pass_protect_for_headers()
        self._snapshot("After protecting for(...)")

        self.pass_space_around_operators()
        self._snapshot("After operator spacing")

        self.pass_autobrace_single_statements()
        self._snapshot("After auto-brace insertion")

        self.pass_semicolon_newlines()
        self._snapshot("After semicolon newlines")

        self.pass_restore_placeholders()
        self._snapshot("After restoring placeholders")

        self.pass_braces_newlines()
        self._snapshot("After braces newlines")

        self.pass_trim_blank_lines()
        self._snapshot("After trimming")

        self.pass_indentation()
        self._snapshot("After indentation (final)")

        return self.tape_str().replace(self.blank, "")

    def _snapshot(self, title=""):
        if self.log_enabled:
            print(f"\n--- {title} ---")
            s = self.tape_str()
            s_vis = s.replace('\n', '\\n\n')
            print(s_vis[:4000])
            print("\n--- end ---\n")

# ---------------- Example runs ----------------
if __name__ == "__main__":
    sample = """
    int main(){int a=3;int b= 4; if(a<b) b = b + a; for(int i=0;i<10;i++){printf(\"%d\",i);}return 0;}
    """
    print("INPUT:")
    print(sample)
    print("="*60)
    fm = TMFormatter(sample, blank="▢", indent_str="    ")
    out = fm.format(verbose=False)  
    print("\nFORMATTED OUTPUT:\n")
    print(out)