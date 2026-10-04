# payscript/errors.py
#
# The one error type used by every stage (lexer, parser, validator, interpreter).
# It carries a message plus the line and column where the problem is,
# so errors always print as: Line 4, col 7: message

class PayScriptError(Exception):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Line {line}, col {col}: {message}")