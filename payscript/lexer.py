from decimal import Decimal

from payscript.errors import PayScriptError
from payscript.tokens import KEYWORDS, SYMBOLS, Token, T

def is_digit(ch):
    """True for 0-9 only (str.isdigit() also accepts digits of other scripts)."""
    return ch.isascii() and ch.isdigit()


def is_letter(ch):
    """True for a-z / A-Z only, so names and keywords are plain ASCII."""
    return ch.isascii() and ch.isalpha()


class Lexer:
    def __init__(self, source):                     #Attributes of the Lexer class
        self.src = source.replace("\r\n", "\n")     #Normalize window line endings to just \n
        self.pos = 0                                #Current position in the source code
        self.line = 1                               #Line number
        self.col = 1                                #Column number
        self.tokens = []                            #All tokens recognized in the source code appended here
        self.open_brackets = []                     #Opening ( and [ tokens not yet closed; newlines are ignored while any are open

    def peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else "" #access the character at the current position plus an offset, return empty string if out of bounds

    def advance(self):
        ch = self.src[self.pos]                     #1. Current character at the current position
        self.pos += 1                               #2. Move the position forward by one
        if ch == "\n":                              #3. check if the current character is a newline character
            self.line += 1                          #4. Add 1 to the line number if new line
            self.col = 1
        else:
            self.col += 1                           #5. else add 1 to the column number if not new line
        return ch                                   #return the character

    def add_token(self, type_, value, line, col):
        self.tokens.append(Token(type_, value, line, col)) #Create a new Token object with the given type, value, line, and column information and append it to the tokens list

    def tokenize(self):
        while self.pos < len(self.src):                             #Loop while position is less than the length of the source code
            ch = self.peek()                                        #Peek at the first character
            line, col = self.line, self.col                         #Store the current line and column numbers in local variables
            if ch in " \t\r":                                       
                self.advance()                                      #Moves the position forward by one character if ch is whitespace, tab, or leftover carraige returns
            elif ch == "\n":                                        # Chcek if the current character is a newline character
                if not self.open_brackets:
                    self.add_token(T.NEWLINE, None, line, col)      #Recognize ch as NEWLINE token and append it to the tokens list if depth is 0
                self.advance()
            elif ch == "/" and self.peek(1) == "/":                 #Check if current two characters is a comment
                self.skip_comment()
            elif ch == '"':
                self.read_string(line, col)
            elif is_digit(ch):
                self.read_number(line, col)    
            elif is_letter(ch) or ch == "_":
                self.read_word(line, col)
            else:
                self.read_symbol(line, col)

        if self.open_brackets:                                      # a ( or [ was never closed: say where it was opened
            opener = self.open_brackets[-1]
            raise PayScriptError(
                f"unclosed '{opener.value}' (it is never closed with "
                f"'{')' if opener.value == '(' else ']'}')",
                opener.line, opener.col)

        if self.tokens and self.tokens[-1].type != T.NEWLINE:       # Shortcircuit: check if tokens contains anything, and check if last token is not a NEWLINE token
            self.add_token(T.NEWLINE, None, self.line, self.col)    # Add a NEWLINE token if the last token is not already a NEWLINE token
        self.add_token(T.EOF, None, self.line, self.col)            # Add an EOF token to the end of the tokens list to indicate the end of the source code
        return self.tokens
    

    # HELPER METHODS

    def skip_comment(self):
        while self.peek() not in ("\n", ""):
            self.advance()

    def read_string(self, line, col):
        self.advance()
        start = self.pos
        while self.peek() not in ('"', "\n", ""):
            self.advance()
        if self.peek() != '"':
            raise PayScriptError("unterminated string", line, col)
        text = self.src[start:self.pos]
        self.advance()
        self.add_token(T.STRING, text, line, col)

    def read_number(self, line, col):
        start = self.pos
        while is_digit(self.peek()):
            self.advance()
        is_float = False
        if self.peek() == "." and is_digit(self.peek(1)):
            is_float = True
            self.advance()
            while is_digit(self.peek()):
                self.advance()
        text = self.src[start:self.pos]
        value = Decimal(text) if is_float else int(text)

        if self.peek() == "%":
            self.advance()
            self.add_token(T.PERCENT, Decimal(value) / 100, line, col)
        else:
            self.add_token(T.NUMBER, value, line, col)

    def read_word(self, line, col):
        start = self.pos
        while is_letter(self.peek()) or is_digit(self.peek()) or self.peek() == "_":
            self.advance()
        word = self.src[start:self.pos]

        if word in KEYWORDS:
            self.add_token(T[word], word, line, col)
        elif word[0].islower() and word == word.lower():
            self.add_token(T.IDENT, word, line, col)
        else:
            raise PayScriptError(
                f"unknown word '{word}' (keywords are UPPERCASE, names are lowercase)",
                line, col)

    def read_symbol(self, line, col):
        two = self.peek() + self.peek(1)
        if two in SYMBOLS:
            text = two
        elif self.peek() in SYMBOLS:
            text = self.peek()
        else:
            raise PayScriptError(f"unknown character '{self.peek()}'", line, col)

        type_ = SYMBOLS[text]
        for _ in text:
            self.advance()

        token = Token(type_, text, line, col)
        if type_ in (T.LPAREN, T.LBRACKET):
            self.open_brackets.append(token)
        elif type_ in (T.RPAREN, T.RBRACKET) and self.open_brackets:
            self.open_brackets.pop()

        self.tokens.append(token)


