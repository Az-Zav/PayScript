
from __future__ import annotations  # lets type hints refer to classes defined later

# Every AST class the parser builds (defined by Dev 3 in ast_nodes.py).
from payscript.ast_nodes import (
    ArrayLiteral,    # [500, 300, 200]
    BinaryExpr,      # a + b, a AND b, a < b ...
    CallExpr,        # INPUT(...), LENGTH(...), my_function(...)
    CompanyDecl,     # COMPANY ... END
    EmployeeDecl,    # EMPLOYEE name ... END
    FieldAccess,     # maria.salary
    FieldEntry,      # one "name value" line inside COMPANY/EMPLOYEE
    ForEachStmt,     # FOR EACH x IN list
    ForRangeStmt,    # FOR EACH i IN 1 -> 3
    FunctionDecl,    # FUNCTION name(...) ... END
    IfBranch,        # one IF / ELSE IF part
    IfStmt,          # the whole IF statement
    IndexAccess,     # list[1]
    Literal,         # a fixed value: 5, "text", TRUE
    Name,            # a name: maria, total
    PayslipStmt,     # PAYSLIP maria
    PayStmt,         # ADD / EXEMPT / CONTRIBUTE / LESS
    PrintStmt,       # PRINT ...
    Program,         # the whole program
    ReturnStmt,      # RETURN value
    SetStmt,         # SET x TO value
    TaxBracket,      # BELOW 100 / ABOVE 100 / 100 -> 200
    TaxRate,         # 15% / 1875 + 20%
    TaxRow,          # one row inside TAX
    TaxTable,        # TAX ... END
    UnaryExpr,       # -5, NOT ready
    WhileStmt,       # WHILE ... END
)
from payscript.constants import PAY_KINDS as PAY_KIND_NAMES  # "ADD", "EXEMPT", ...
from payscript.errors import PayScriptError  # the shared error type (message, line, col)
from payscript.tokens import KEYWORDS, T, Token  # T = list of token types

# Comparison operators: token type -> the text we store in the tree.
COMPARISON_OPS = {
    T.EQ: "=",     # equal
    T.NEQ: "!=",   # not equal
    T.LT: "<",     # less than
    T.LTE: "<=",   # less than or equal
    T.GT: ">",     # greater than
    T.GTE: ">=",   # greater than or equal
}

# The four pay commands (all parsed by the same method).
PAY_KINDS = tuple(T[name] for name in PAY_KIND_NAMES)


def parse(tokens):
    """Turn a list of tokens into a Program (the AST). This is the entry point."""
    return Parser(tokens).parse()  # make a Parser, run it, return the tree


class Parser:
    def __init__(self, tokens):
        self.tokens = list(tokens)  # keep our own copy of the token list
        self.pos = 0                # position of the token we are looking at now
        # Safety: the list must end with EOF (hand-made lists may forget it).
        if not self.tokens or self.tokens[-1].type != T.EOF:
            if self.tokens:                                    # list has tokens but no EOF
                last = self.tokens[-1]                         # look at the last token
                eof = Token(T.EOF, None, last.line, last.col + 1)  # put EOF just after it
            else:                                              # list is completely empty
                eof = Token(T.EOF, None, 1, 1)                 # EOF at the very start
            self.tokens.append(eof)                            # add the EOF token


    # Small helpers for moving through the tokens
    

    def peek(self, offset=0):
        """Look at a token without using it up. offset=1 means 'the next one'."""
        index = min(self.pos + offset, len(self.tokens) - 1)  # never go past the last token
        return self.tokens[index]                             # return that token

    def advance(self):
        """Use up the current token and return it."""
        tok = self.tokens[self.pos]   # the token we are on
        if tok.type != T.EOF:         # never move past the end of the file
            self.pos += 1             # step to the next token
        return tok                    # hand back the token we just used

    def check(self, *types):
        """Is the current token one of these types? (does not use it up)"""
        return self.peek().type in types  # True or False

    def match(self, *types):
        """If the current token is one of these types, use it up and return it."""
        if self.check(*types):        # is it one of them?
            return self.advance()     # yes: consume and return it
        return None                   # no: do nothing

    def skip_newlines(self):
        """Skip any blank lines."""
        while self.check(T.NEWLINE):  # as long as we are on a NEWLINE token...
            self.advance()            # ...use it up

    def describe(self, tok):
        """A friendly description of a token, used inside error messages."""
        if tok.type == T.NEWLINE:     # a line break
            return "the end of the line"
        if tok.type == T.EOF:         # no more tokens
            return "the end of the file"
        if tok.type == T.STRING:      # text in quotes
            return f'the text "{tok.value}"'
        if tok.type == T.IDENT:       # a lowercase name
            return f"the name '{tok.value}'"
        if tok.type == T.NUMBER:      # a number
            return f"the number {tok.value}"
        if tok.type == T.PERCENT:     # a percentage (stored as a fraction, so *100)
            return f"the percentage {tok.value * 100:g}%"
        if tok.type.name in KEYWORDS: # an UPPERCASE keyword
            return f"the keyword {tok.type.name}"
        return f"'{tok.value}'"       # anything else (symbols like + or ,)

    def error(self, message, tok):
        """Stop with an error that points at this token's line and column."""
        raise PayScriptError(message, tok.line, tok.col)

    def expect(self, ttype, what):
        """Use up a token of type ttype, or stop with 'Expected <what>, but found ...'."""
        tok = self.peek()                       # look at the current token
        if tok.type != ttype:                   # not the type we need?
            self.error(f"Expected {what}, but found {self.describe(tok)}", tok)
        return self.advance()                   # it is right: use it up and return it

    def end_of_statement(self):
        """A statement must be followed by a line break (or the end of the file)."""
        if self.check(T.NEWLINE):               # normal case: a line break
            self.advance()                      # use it up
        elif not self.check(T.EOF):             # neither a line break nor the end?
            tok = self.peek()                   # then there is something extra here
            self.error(
                f"Unexpected {self.describe(tok)}; expected the end of the line",
                tok,
            )

    def expect_end(self, opener, what):
        """Use up the END that closes a block. 'opener' is the token that started it."""
        if self.check(T.END):                   # found the END we wanted
            return self.advance()               # use it up
        tok = self.peek()                       # otherwise something else is here
        if tok.type == T.EOF:                   # the file ended before any END
            self.error(
                f"Missing END for the {what} that started on line {opener.line}",
                tok,
            )
        self.error(                             # some other token where END should be
            f"Expected END to close the {what} that started on line "
            f"{opener.line}, but found {self.describe(tok)}",
            tok,
        )

    # ------------------------------------------------------------------
    # Program and blocks
    # ------------------------------------------------------------------

    def parse(self):
        """Grammar: program = { line } , EOF"""
        statements = []                         # all top-level statements, in order
        while True:                             # keep going until the file ends
            self.skip_newlines()                # ignore blank lines
            if self.check(T.EOF):               # end of file reached
                break                           # stop reading statements
            statements.append(self.parse_line())  # read one statement and keep it
        if statements:                          # the Program starts where the first statement starts
            line, col = statements[0].line, statements[0].col
        else:                                   # empty program: location (1, 1)
            line, col = 1, 1
        return Program(statements=statements, line=line, col=col)

    def parse_line(self):
        """Grammar: line = statement , NEWLINE"""
        stmt = self.parse_statement()           # read the statement itself
        self.end_of_statement()                 # then require the line break after it
        return stmt                             # give the statement back

    def parse_block(self):
        """Grammar: block = { line }   (stops at END or ELSE, which it does NOT use up)"""
        body = []                               # statements inside the block
        while True:
            self.skip_newlines()                # ignore blank lines
            if self.check(T.END, T.ELSE, T.EOF):  # the block is over
                return body                     # hand back what we collected
            body.append(self.parse_line())      # otherwise read one more statement

    def parse_statement(self):
        """Look at the first token and decide which kind of statement this is."""
        tok = self.peek()                       # the first token of the statement
        t = tok.type                            # its type
        if t == T.COMPANY:                      # COMPANY ... END
            return self.parse_company()
        if t == T.EMPLOYEE:                     # EMPLOYEE name ... END
            return self.parse_employee()
        if t == T.TAX:                          # TAX ... END
            return self.parse_tax_table()
        if t == T.FUNCTION:                     # FUNCTION name(...) ... END
            return self.parse_function()
        if t == T.IF:                           # IF ... END
            return self.parse_if()
        if t == T.WHILE:                        # WHILE ... END
            return self.parse_while()
        if t == T.FOR:                          # FOR EACH ... END
            return self.parse_for()
        if t == T.SET:                          # SET x TO ...
            return self.parse_set()
        if t in PAY_KINDS:                      # ADD / EXEMPT / CONTRIBUTE / LESS
            return self.parse_pay()
        if t == T.PAYSLIP:                      # PAYSLIP target
            return self.parse_payslip()
        if t == T.PRINT:                        # PRINT ...
            return self.parse_print()
        if t == T.RETURN:                       # RETURN value
            return self.parse_return()

        # If we get here, the line does not start like any statement.
        # Give a helpful message depending on what we found.
        if t == T.END:                          # END with nothing to close
            self.error("Found END without a block (IF, WHILE, FOR...) to close", tok)
        if t == T.ELSE:                         # ELSE with no IF
            self.error("Found ELSE without a matching IF", tok)
        if t == T.IDENT:                        # a lone name: probably forgot SET
            self.error(
                f"A line cannot start with the name '{tok.value}'. "
                f"To store a value, write: SET {tok.value} TO value",
                tok,
            )
        self.error(                             # anything else
            f"A line cannot start with {self.describe(tok)}. Expected a command "
            "such as SET, PRINT, IF, ADD, or PAYSLIP",
            tok,
        )

    # ------------------------------------------------------------------
    # Declarations: COMPANY, EMPLOYEE, TAX, FUNCTION
    # ------------------------------------------------------------------

    def parse_field_lines(self):
        """Grammar: { field_line } where field_line = IDENT value NEWLINE.
        Used inside COMPANY and EMPLOYEE. Stops at END."""
        fields = []                             # the FieldEntry nodes we collect
        while True:
            self.skip_newlines()                # ignore blank lines
            if self.check(T.END, T.EOF):        # no more field lines
                return fields
            name_tok = self.expect(             # the field name, e.g. salary
                T.IDENT, "a field name (like 'salary') or END"
            )
            value_tok = self.peek()             # the value after the name
            if value_tok.type not in (T.NUMBER, T.STRING):  # must be a number or text
                self.error(
                    f"Field '{name_tok.value}' needs a number or text value, "
                    f"but found {self.describe(value_tok)}",
                    value_tok,
                )
            self.advance()                      # use up the value token
            value = Literal(                    # wrap the value as a Literal node
                value=value_tok.value, line=value_tok.line, col=value_tok.col
            )
            fields.append(                      # store name + value as a FieldEntry
                FieldEntry(
                    name=name_tok.value,        # field name text
                    value=value,                # the Literal
                    line=name_tok.line,         # location = the field-name token
                    col=name_tok.col,
                )
            )
            self.end_of_statement()             # the field line must end with a line break

    def parse_company(self):
        """Grammar: "COMPANY" NEWLINE { field_line } "END" """
        kw = self.advance()                     # use up COMPANY (keep it for its location)
        self.end_of_statement()                 # line break after COMPANY
        fields = self.parse_field_lines()       # working_days, hours_per_day ...
        self.expect_end(kw, "COMPANY block")    # the closing END
        return CompanyDecl(fields=fields, line=kw.line, col=kw.col)

    def parse_employee(self):
        """Grammar: "EMPLOYEE" IDENT NEWLINE { field_line } "END" """
        kw = self.advance()                     # use up EMPLOYEE
        handle = self.expect(                   # the employee's short name, e.g. maria
            T.IDENT, "a name for the employee (for example: EMPLOYEE maria)"
        )
        self.end_of_statement()                 # line break after the handle
        fields = self.parse_field_lines()       # name, salary, position ...
        self.expect_end(kw, "EMPLOYEE block")   # the closing END
        return EmployeeDecl(
            handle=handle.value, fields=fields, line=kw.line, col=kw.col
        )

    def parse_tax_table(self):
        """Grammar: "TAX" NEWLINE { tax_row } "END" """
        kw = self.advance()                     # use up TAX
        self.end_of_statement()                 # line break after TAX
        rows = []                               # the TaxRow nodes
        while True:
            self.skip_newlines()                # ignore blank lines
            if self.check(T.END, T.EOF):        # no more rows
                break
            rows.append(self.parse_tax_row())   # read one row
            self.end_of_statement()             # each row ends with a line break
        self.expect_end(kw, "TAX block")        # the closing END
        return TaxTable(rows=rows, line=kw.line, col=kw.col)

    def parse_tax_row(self):
        """Grammar: tax_row = bracket "=" rate"""
        first = self.peek()                     # first token (gives the row its location)
        bracket = self.parse_bracket()          # BELOW x / ABOVE x / a -> b
        self.expect(T.EQ, "'=' followed by a tax rate")  # the '=' sign
        rate = self.parse_rate()                # 15% or 1875 + 20% ...
        return TaxRow(bracket=bracket, rate=rate, line=first.line, col=first.col)

    def number_literal(self, what):
        """Read one NUMBER token and wrap it as a Literal node."""
        tok = self.expect(T.NUMBER, what)       # must be a number
        return Literal(value=tok.value, line=tok.line, col=tok.col)

    def parse_bracket(self):
        """Grammar: bracket = BELOW NUMBER | ABOVE NUMBER | NUMBER "->" NUMBER"""
        first = self.peek()                     # decides which kind of bracket this is
        if first.type == T.BELOW:               # BELOW x
            self.advance()                      # use up BELOW
            upper = self.number_literal("a number after BELOW")  # the limit x
            return TaxBracket(
                kind="BELOW", upper=upper, line=first.line, col=first.col
            )
        if first.type == T.ABOVE:               # ABOVE x
            self.advance()                      # use up ABOVE
            lower = self.number_literal("a number after ABOVE")  # the limit x
            return TaxBracket(
                kind="ABOVE", lower=lower, line=first.line, col=first.col
            )
        if first.type == T.NUMBER:              # a -> b  (a range)
            lower = self.number_literal("a number")              # the start a
            self.expect(T.ARROW, "'->' in a range like 20833 -> 33333")  # the arrow
            upper = self.number_literal("a number after '->'")   # the end b
            return TaxBracket(
                kind="RANGE",
                lower=lower,
                upper=upper,
                line=first.line,
                col=first.col,
            )
        self.error(                             # none of the three forms
            "Expected a tax bracket (BELOW x, ABOVE x, or a range like "
            f"a -> b), but found {self.describe(first)}",
            first,
        )

    def parse_rate(self):
        """Grammar: rate = PERCENT | NUMBER [ "+" PERCENT ]"""
        first = self.peek()                     # first token of the rate
        if first.type == T.PERCENT:             # just a percentage, e.g. 15%
            self.advance()                      # use it up
            fraction = Literal(value=first.value, line=first.line, col=first.col)
            return TaxRate(fraction=fraction, line=first.line, col=first.col)
        if first.type == T.NUMBER:              # a fixed amount, maybe followed by + percent
            self.advance()                      # use up the number
            fixed = Literal(value=first.value, line=first.line, col=first.col)
            fraction = None                     # no percentage unless we find "+ PERCENT"
            if self.match(T.PLUS):              # is there a "+" after the number?
                ptok = self.expect(T.PERCENT, "a percentage after '+' (like 20%)")
                fraction = Literal(value=ptok.value, line=ptok.line, col=ptok.col)
            return TaxRate(
                fixed_amount=fixed,             # e.g. 1875
                fraction=fraction,              # e.g. 0.20, or None
                line=first.line,
                col=first.col,
            )
        self.error(                             # neither a percent nor a number
            "Expected a tax rate such as 15% or 1875 + 20%, but found "
            f"{self.describe(first)}",
            first,
        )

    def parse_function(self):
        """Grammar: "FUNCTION" IDENT "(" [ params ] ")" NEWLINE block "END" """
        kw = self.advance()                     # use up FUNCTION
        name = self.expect(T.IDENT, "a function name")           # e.g. perfect_bonus
        self.expect(T.LPAREN, "'(' after the function name")     # the opening (
        params = []                             # parameter names, as Name nodes
        if not self.check(T.RPAREN):            # if the list is not empty...
            while True:
                p = self.expect(T.IDENT, "a parameter name")     # one parameter
                params.append(Name(name=p.value, line=p.line, col=p.col))
                if not self.match(T.COMMA):     # a comma means another parameter follows
                    break                       # no comma: the list is done
        self.expect(T.RPAREN, "')' to close the parameter list") # the closing )
        self.end_of_statement()                 # line break after the header
        body = self.parse_block()               # the statements inside the function
        self.expect_end(kw, "FUNCTION")         # the closing END
        return FunctionDecl(
            name=name.value, params=params, body=body, line=kw.line, col=kw.col
        )

    # ------------------------------------------------------------------
    # Control flow: IF, WHILE, FOR
    # ------------------------------------------------------------------

    def parse_if(self):
        """Grammar: IF expr THEN NEWLINE block { ELSE IF expr THEN NEWLINE block }
                    [ ELSE NEWLINE block ] END"""
        kw = self.advance()                     # use up IF
        branches = []                           # the IF part, then every ELSE IF part
        else_body = None                        # None = there is no ELSE

        condition = self.parse_expression()     # the condition after IF
        self.expect(T.THEN, "THEN after the IF condition")  # the word THEN
        self.end_of_statement()                 # line break after THEN
        body = self.parse_block()               # statements to run if true
        branches.append(                        # save this first branch
            IfBranch(condition=condition, body=body, line=kw.line, col=kw.col)
        )

        while self.check(T.ELSE):               # keep going while we see ELSE
            else_tok = self.advance()           # use up ELSE
            if self.check(T.IF):                # "ELSE IF" -> another branch
                self.advance()                  # use up IF
                condition = self.parse_expression()  # its condition
                self.expect(T.THEN, "THEN after the ELSE IF condition")
                self.end_of_statement()         # line break after THEN
                body = self.parse_block()       # its statements
                branches.append(                # branch location = the ELSE keyword
                    IfBranch(
                        condition=condition,
                        body=body,
                        line=else_tok.line,
                        col=else_tok.col,
                    )
                )
            else:                               # plain ELSE -> the final part
                self.end_of_statement()         # line break after ELSE
                else_body = self.parse_block()  # may be empty []
                if self.check(T.ELSE):          # a second ELSE is not allowed
                    self.error(
                        "An IF can have only one ELSE, and it must come last",
                        self.peek(),
                    )
                break                           # nothing may follow the ELSE part

        self.expect_end(kw, "IF statement")     # the single END that closes everything
        return IfStmt(
            branches=branches, else_body=else_body, line=kw.line, col=kw.col
        )

    def parse_while(self):
        """Grammar: "WHILE" expression NEWLINE block "END" """
        kw = self.advance()                     # use up WHILE
        condition = self.parse_expression()     # the loop condition
        self.end_of_statement()                 # line break after the condition
        body = self.parse_block()               # the repeated statements
        self.expect_end(kw, "WHILE loop")       # the closing END
        return WhileStmt(condition=condition, body=body, line=kw.line, col=kw.col)

    def parse_for(self):
        """Grammar: "FOR" "EACH" IDENT "IN" expression [ "->" expression ] NEWLINE block "END" """
        kw = self.advance()                     # use up FOR
        self.expect(T.EACH, "EACH after FOR (write: FOR EACH x IN ...)")
        var = self.expect(T.IDENT, "a loop variable name")  # e.g. e or i
        variable = Name(name=var.value, line=var.line, col=var.col)
        self.expect(T.IN, "IN after the loop variable")     # the word IN
        first = self.parse_expression()         # an array, or the start of a range
        if self.match(T.ARROW):                 # "->" means it is a number range
            last = self.parse_expression()      # the end of the range
            self.end_of_statement()             # line break after the header
            body = self.parse_block()           # the repeated statements
            self.expect_end(kw, "FOR loop")     # the closing END
            return ForRangeStmt(                # FOR EACH i IN 1 -> 3
                variable=variable,
                start=first,
                end=last,
                body=body,
                line=kw.line,
                col=kw.col,
            )
        self.end_of_statement()                 # no arrow: looping over an array
        body = self.parse_block()               # the repeated statements
        self.expect_end(kw, "FOR loop")         # the closing END
        return ForEachStmt(                     # FOR EACH e IN employees
            variable=variable,
            iterable=first,
            body=body,
            line=kw.line,
            col=kw.col,
        )

    # ------------------------------------------------------------------
    # Simple statements: SET, pay commands, PAYSLIP, PRINT, RETURN
    # ------------------------------------------------------------------

    def parse_target(self, what="a name"):
        """Grammar: target = IDENT [ "[" expression "]" ]  (a name, maybe with an index)"""
        tok = self.expect(T.IDENT, what)        # the name, e.g. maria or list
        name = Name(name=tok.value, line=tok.line, col=tok.col)
        if self.check(T.LBRACKET):              # is there an index, like list[2]?
            self.advance()                      # use up [
            index = self.parse_expression()     # the index expression
            self.expect(T.RBRACKET, "']' after the index")  # the closing ]
            return IndexAccess(base=name, index=index, line=tok.line, col=tok.col)
        return name                             # plain name, no index

    def parse_set(self):
        """Grammar: "SET" target "TO" expression"""
        kw = self.advance()                     # use up SET
        target = self.parse_target("a variable name after SET")  # the variable
        self.expect(T.TO, "TO after the variable name (write: SET x TO value)")
        value = self.parse_expression()         # the value to store
        return SetStmt(target=target, value=value, line=kw.line, col=kw.col)

    def parse_pay(self):
        """Grammar: ( "ADD" | "EXEMPT" | "CONTRIBUTE" | "LESS" ) target STRING expression"""
        kw = self.advance()                     # use up the keyword (ADD, EXEMPT, ...)
        target = self.parse_target("an employee name after " + kw.type.name)
        label_tok = self.expect(                # the label in quotes, e.g. "Bonus"
            T.STRING, 'a label in quotes (for example: "Bonus")'
        )
        label = Literal(                        # wrap the label as a Literal
            value=label_tok.value, line=label_tok.line, col=label_tok.col
        )
        amount = self.parse_expression()        # the amount (any expression)
        return PayStmt(
            kind=kw.type.name,                  # "ADD", "EXEMPT", "CONTRIBUTE" or "LESS"
            target=target,
            label=label,
            amount=amount,
            line=kw.line,
            col=kw.col,
        )

    def parse_payslip(self):
        """Grammar: "PAYSLIP" target"""
        kw = self.advance()                     # use up PAYSLIP
        target = self.parse_target("an employee name after PAYSLIP")
        return PayslipStmt(target=target, line=kw.line, col=kw.col)

    def parse_print(self):
        """Grammar: "PRINT" expression { "," expression }"""
        kw = self.advance()                     # use up PRINT
        items = [self.parse_expression()]       # at least one thing to print
        while self.match(T.COMMA):              # each comma adds another item
            items.append(self.parse_expression())
        return PrintStmt(items=items, line=kw.line, col=kw.col)

    def parse_return(self):
        """Grammar: "RETURN" expression"""
        kw = self.advance()                     # use up RETURN
        value = self.parse_expression()         # the value to give back
        return ReturnStmt(value=value, line=kw.line, col=kw.col)

    # ------------------------------------------------------------------
    # Expressions. From LOOSEST (done last) to TIGHTEST (done first):
    #   OR, AND, NOT, comparison, + -, * /, unary -, .field and [i], primary
    # Each method calls the next-tighter one, which is what makes
    # 1 + 2 * 3 come out as 1 + (2 * 3).
    # Each compound node is placed at the FIRST token of the expression.
    # ------------------------------------------------------------------

    def parse_expression(self):
        """Grammar: expression = or_expr"""
        return self.parse_or()                  # start at the loosest level

    def parse_or(self):
        """Grammar: or_expr = and_expr { "OR" and_expr }"""
        start = self.peek()                     # remember where the expression starts
        left = self.parse_and()                 # the left side
        while self.match(T.OR):                 # for every OR we meet...
            right = self.parse_and()            # ...read the right side
            left = BinaryExpr(                  # ...and combine into one node
                left=left, operator="OR", right=right, line=start.line, col=start.col
            )
        return left

    def parse_and(self):
        """Grammar: and_expr = not_expr { "AND" not_expr }"""
        start = self.peek()                     # remember where the expression starts
        left = self.parse_not()                 # the left side
        while self.match(T.AND):                # for every AND we meet...
            right = self.parse_not()            # ...read the right side
            left = BinaryExpr(                  # ...and combine into one node
                left=left, operator="AND", right=right, line=start.line, col=start.col
            )
        return left

    def parse_not(self):
        """Grammar: not_expr = "NOT" not_expr | comparison"""
        if self.check(T.NOT):                   # starts with NOT?
            tok = self.advance()                # use up NOT
            operand = self.parse_not()          # what is being negated (NOT NOT x works)
            return UnaryExpr(
                operator="NOT", operand=operand, line=tok.line, col=tok.col
            )
        return self.parse_comparison()          # no NOT: go to the next level

    def parse_comparison(self):
        """Grammar: comparison = additive [ comp_op additive ]  (only ONE comparison allowed)"""
        start = self.peek()                     # remember where the expression starts
        left = self.parse_additive()            # the left side
        if self.peek().type in COMPARISON_OPS:  # is there a = != < <= > >= ?
            op_tok = self.advance()             # use up the operator
            right = self.parse_additive()       # the right side
            left = BinaryExpr(
                left=left,
                operator=COMPARISON_OPS[op_tok.type],  # stored as source text, e.g. "<="
                right=right,
                line=start.line,
                col=start.col,
            )
            if self.peek().type in COMPARISON_OPS:     # a second comparison, like 1 < 2 < 3
                self.error(
                    "Comparisons cannot be chained; use AND to combine them "
                    "(for example: a < b AND b < c)",
                    self.peek(),
                )
        return left

    def parse_additive(self):
        """Grammar: additive = term { ( "+" | "-" ) term }"""
        start = self.peek()                     # remember where the expression starts
        left = self.parse_term()                # the left side (multiplication binds tighter)
        while self.check(T.PLUS, T.MINUS):      # for every + or - we meet...
            op = "+" if self.advance().type == T.PLUS else "-"  # ...use it up, note which
            right = self.parse_term()           # ...read the right side
            left = BinaryExpr(                  # ...combine; looping makes it left-to-right
                left=left, operator=op, right=right, line=start.line, col=start.col
            )
        return left

    def parse_term(self):
        """Grammar: term = unary { ( "*" | "/" ) unary }"""
        start = self.peek()                     # remember where the expression starts
        left = self.parse_unary()               # the left side
        while self.check(T.STAR, T.SLASH):      # for every * or / we meet...
            op = "*" if self.advance().type == T.STAR else "/"  # ...use it up, note which
            right = self.parse_unary()          # ...read the right side
            left = BinaryExpr(                  # ...combine into one node
                left=left, operator=op, right=right, line=start.line, col=start.col
            )
        return left

    def parse_unary(self):
        """Grammar: unary = "-" unary | postfix"""
        if self.check(T.MINUS):                 # a minus in front, like -5?
            tok = self.advance()                # use up the minus
            operand = self.parse_unary()        # what it applies to (--5 works)
            return UnaryExpr(
                operator="-", operand=operand, line=tok.line, col=tok.col
            )
        return self.parse_postfix()             # no minus: go to the next level

    def parse_postfix(self):
        """Grammar: postfix = primary { "." IDENT | "[" expression "]" }"""
        start = self.peek()                     # remember where the expression starts
        expr = self.parse_primary()             # the basic value first, e.g. employees
        while True:                             # then any number of .field or [index]
            if self.match(T.DOT):               # ".field", e.g. .net
                field_tok = self.expect(T.IDENT, "a field name after '.'")
                expr = FieldAccess(             # wrap what we had so far
                    base=expr,
                    field_name=field_tok.value,
                    line=start.line,
                    col=start.col,
                )
            elif self.match(T.LBRACKET):        # "[index]", e.g. [1]
                index = self.parse_expression() # the index expression
                self.expect(T.RBRACKET, "']' after the index")
                expr = IndexAccess(             # wrap what we had so far
                    base=expr, index=index, line=start.line, col=start.col
                )
            else:                               # nothing more to attach
                return expr

    def parse_args(self):
        """Grammar: args = expression { "," expression }  (the caller handles the brackets)"""
        args = [self.parse_expression()]        # the first item
        while self.match(T.COMMA):              # each comma adds another item
            args.append(self.parse_expression())
        return args

    def parse_call(self):
        """Grammar: call = ( IDENT | "INPUT" | "LENGTH" ) "(" [ args ] ")" """
        name_tok = self.advance()               # use up the function name token
        name = (                                # normal functions use their own name,
            name_tok.value if name_tok.type == T.IDENT else name_tok.type.name
        )                                       # INPUT / LENGTH become "INPUT" / "LENGTH"
        self.expect(T.LPAREN, f"'(' after {name}")          # the opening (
        args = []                               # the arguments (may stay empty)
        if not self.check(T.RPAREN):            # if the list is not empty...
            args = self.parse_args()            # ...read the arguments
        self.expect(T.RPAREN, "')' to close the call")      # the closing )
        return CallExpr(
            name=name, arguments=args, line=name_tok.line, col=name_tok.col
        )

    def parse_primary(self):
        """Grammar: primary = NUMBER | PERCENT | STRING | TRUE | FALSE | call
                              | IDENT | array | "(" expression ")"
        This is the tightest level: the smallest pieces of an expression."""
        tok = self.peek()                       # the token we are looking at
        t = tok.type                            # its type

        if t in (T.NUMBER, T.PERCENT, T.STRING):  # a plain value
            self.advance()                      # use it up
            # PERCENT is already a fraction from the lexer (20% = 0.20): do NOT divide again
            return Literal(value=tok.value, line=tok.line, col=tok.col)
        if t == T.TRUE:                         # the word TRUE
            self.advance()
            return Literal(value=True, line=tok.line, col=tok.col)
        if t == T.FALSE:                        # the word FALSE
            self.advance()
            return Literal(value=False, line=tok.line, col=tok.col)
        if t in (T.INPUT, T.LENGTH):            # INPUT(...) or LENGTH(...)
            return self.parse_call()
        if t == T.IDENT:                        # a name... or a function call
            if self.peek(1).type == T.LPAREN:   # name followed by ( means a call
                return self.parse_call()
            self.advance()                      # otherwise it is just a name
            return Name(name=tok.value, line=tok.line, col=tok.col)
        if t == T.LBRACKET:                     # an array like [500, 300, 200]
            self.advance()                      # use up [
            items = []                          # the array items (may stay empty)
            if not self.check(T.RBRACKET):      # if not an empty array...
                items = self.parse_args()       # ...read the items
            self.expect(T.RBRACKET, "']' to close the array")  # the closing ]
            return ArrayLiteral(items=items, line=tok.line, col=tok.col)
        if t == T.LPAREN:                       # parentheses, like (1 + 2)
            self.advance()                      # use up (
            inner = self.parse_expression()     # whatever is inside, parsed from the top
            self.expect(T.RPAREN, "')' to close the parenthesis")
            return inner                        # parentheses only group; they add no node

        self.error(                             # nothing above matched: not a value
            "Expected a value (a number, text, name, TRUE/FALSE, array or "
            f"call), but found {self.describe(tok)}",
            tok,
        )