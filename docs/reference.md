# PayScript language reference

The formal definition of PayScript: its lexical rules, its grammar, and the
rules the validator and interpreter enforce. For how the implementation is
organised, see [architecture.md](architecture.md).

## 1. Lexical rules

| Item | Rule |
|---|---|
| Keywords | UPPERCASE only (see the list below) |
| Names (`IDENT`) | lowercase letters, digits and `_`, starting with a lowercase letter |
| ASCII | Names and keywords are ASCII only. Text in `"..."` and `//` comments may hold any characters |
| Numbers | Digits with an optional fraction (`500`, `1.25`). Whole numbers are ints; fractions are exact decimals |
| Percent | `20%` means `0.20` |
| Strings | `"..."` on one line. There are no escape sequences, so a string cannot contain a double quote |
| Comments | `//` to the end of the line, ignored |
| Line breaks | End a statement. They are ignored inside `( )` and `[ ]` |
| Unclosed bracket | A `(` or `[` that is never closed is an error reported where it was opened |

**Keywords:**
`COMPANY EMPLOYEE END TAX BELOW ABOVE ADD EXEMPT CONTRIBUTE LESS PAYSLIP PRINT
SET TO IF THEN ELSE WHILE FOR EACH IN FUNCTION RETURN INPUT LENGTH AND OR NOT
TRUE FALSE`

## 2. Grammar

EBNF notation: `{ x }` repeats zero or more times, `[ x ]` is optional,
`|` separates alternatives, and `(* ... *)` is a comment.

```
(* ===================== PROGRAM ===================== *)
program          = { line } , EOF ;
line             = [ statement ] , NEWLINE ;
block            = { line } ;   (* stops at END or ELSE *)

statement        = company_decl | employee_decl | tax_table
                 | function_decl | if_stmt | while_stmt | for_stmt
                 | set_stmt | pay_stmt | payslip_stmt
                 | print_stmt | return_stmt ;

(* ==================== DECLARATIONS ==================== *)
company_decl     = "COMPANY" , NEWLINE , { field_line } , "END" ;
employee_decl    = "EMPLOYEE" , IDENT , NEWLINE , { field_line } , "END" ;
field_line       = [ IDENT , value ] , NEWLINE ;
value            = NUMBER | STRING ;

(* ===================== PAY COMMANDS ===================== *)
pay_stmt         = ( "ADD" | "EXEMPT" | "CONTRIBUTE" | "LESS" ) ,
                   target , STRING , expression ;
payslip_stmt     = "PAYSLIP" , target ;
target           = IDENT , [ "[" , expression , "]" ] ;

(* ====================== TAX TABLE ====================== *)
tax_table        = "TAX" , NEWLINE , { tax_row } , "END" ;
tax_row          = [ bracket , "=" , rate ] , NEWLINE ;
bracket          = "BELOW" , NUMBER
                 | "ABOVE" , NUMBER
                 | NUMBER , "->" , NUMBER ;
rate             = PERCENT | NUMBER , [ "+" , PERCENT ] ;

(* ================ CONTROL FLOW & FUNCTIONS ================ *)
if_stmt          = "IF" , expression , "THEN" , NEWLINE , block ,
                   { "ELSE" , "IF" , expression , "THEN" , NEWLINE , block } ,
                   [ "ELSE" , NEWLINE , block ] ,
                   "END" ;
while_stmt       = "WHILE" , expression , NEWLINE , block , "END" ;
for_stmt         = "FOR" , "EACH" , IDENT , "IN" ,
                   expression , [ "->" , expression ] ,
                   NEWLINE , block , "END" ;
function_decl    = "FUNCTION" , IDENT , "(" , [ params ] , ")" ,
                   NEWLINE , block , "END" ;
params           = IDENT , { "," , IDENT } ;
return_stmt      = "RETURN" , expression ;

(* =================== GENERAL STATEMENTS =================== *)
set_stmt         = "SET" , target , "TO" , expression ;
print_stmt       = "PRINT" , expression , { "," , expression } ;

(* ====================== EXPRESSIONS ====================== *)
expression       = or_expr ;
or_expr          = and_expr , { "OR" , and_expr } ;
and_expr         = not_expr , { "AND" , not_expr } ;
not_expr         = "NOT" , not_expr | comparison ;
comparison       = additive , [ comp_op , additive ] ;
comp_op          = "=" | "!=" | "<" | "<=" | ">" | ">=" ;
additive         = term , { ( "+" | "-" ) , term } ;
term             = unary , { ( "*" | "/" ) , unary } ;
unary            = "-" , unary | postfix ;
postfix          = primary , { "." , IDENT | "[" , expression , "]" } ;
primary          = NUMBER | PERCENT | STRING | "TRUE" | "FALSE"
                 | call | IDENT | array | "(" , expression , ")" ;
call             = ( IDENT | "INPUT" | "LENGTH" ) , "(" , [ args ] , ")" ;
args             = expression , { "," , expression } ;
array            = "[" , [ args ] , "]" ;

(* ======================== TOKENS ======================== *)
IDENT            = lower , { lower | digit | "_" } ;   (* lowercase only *)
NUMBER           = digit , { digit } , [ "." , digit , { digit } ] ;
PERCENT          = NUMBER , "%" ;                     (* means / 100 *)
STRING           = '"' , { any char except '"' or newline } , '"' ;
COMMENT          = "//" , { any char except newline } ;   (* ignored *)
NEWLINE          = line break ;   (* ignored inside ( ) and [ ] *)
```

## 3. Rules the grammar cannot express

Rules marked *error* stop the run before it starts (validator). Rules marked
*run time* are detected while the program executes. A *warning* is reported
but does not stop the run unless `--strict` is used. Rows marked *behaviour*
describe how the language works; there is nothing to violate.

### Program structure

| Rule | Kind |
|---|---|
| Exactly one `COMPANY` declaration is required | error |
| At most one `TAX` block | error |
| `COMPANY`, `EMPLOYEE`, `TAX` and `FUNCTION` may only appear at the top level | error |
| Everything runs top to bottom; declare before use | error |

### Fields

| Block | Field | Kind | Rule | Default |
|---|---|---|---|---|
| `COMPANY` | `working_days` | number | required, greater than 0 | none |
| `COMPANY` | `hours_per_day` | number | required, greater than 0 | none |
| `EMPLOYEE` | `name` | text | required | none |
| `EMPLOYEE` | `salary` | number | required, 0 or more | none |
| `EMPLOYEE` | `position` | text | optional | empty |
| `EMPLOYEE` | `absences` | number | optional, 0 or more | 0 |
| `EMPLOYEE` | `late_minutes` | number | optional, 0 or more | 0 |
| `EMPLOYEE` | `overtime_hours` | number | optional, 0 or more | 0 |

An unknown field is an error.

### Computed fields

Every employee exposes these read-only numbers (`maria.net`, `maria.tax`, ...):

`daily_rate hourly_rate minute_rate absence_deduction tardiness_deduction
basic_pay overtime_pay total_add total_exempt total_contribute total_less
gross taxable tax net`

They cannot be assigned to (`SET maria.net TO 5` is an error), and their names
are reserved.

### Names

| Rule | Kind |
|---|---|
| `company`, `employees` and all computed field names are reserved and cannot be used for variables, employees or functions | error |
| A loop variable cannot shadow an employee handle | error |
| A pay target must be a declared employee handle or a `FOR EACH` loop variable | error |

### Pay commands and labels

| Command | Adds to gross | Counts toward taxable income | Deducted from net |
|---|---|---|---|
| `ADD` | yes | yes | no |
| `EXEMPT` | yes | no | no |
| `CONTRIBUTE` | no | reduces it | yes |
| `LESS` | no | no | yes |

| Rule | Kind |
|---|---|
| Labels are case-sensitive | behaviour |
| Reserved labels `"Basic Pay"`, `"Absences"`, `"Tardiness"`, `"Overtime"` and `"Withholding Tax"` cannot be used | error |
| Two labels on one employee that differ only in case | warning |
| The same label used twice for one employee | run time (so different `IF` branches may reuse a label) |
| An amount must be a number | run time |
| Pay commands are not allowed inside a `FUNCTION` | error |
| Each amount is rounded to centavos, halves up, when it is recorded | behaviour |

`overtime_hours` is paid automatically at `hourly_rate * 1.25`, added to gross
and to taxable income, and shown as an `Overtime` row when it is greater than 0.
Do not add overtime by hand.

### Tax tables

| Rule | Kind |
|---|---|
| Overlapping ranges | error |
| Income that falls between two rows (fractions included) | error |
| A table with no `ABOVE` row | warning |
| Income below the first row is untaxed | behaviour |
| A row's percentage applies to `income - the row's own lower bound`, plus the row's fixed amount; a `BELOW` row counts from 0 | behaviour |
| Rows are checked in order, and the first match is used | behaviour |
| `a -> b` includes both ends | behaviour |

### Control flow

| Rule | Kind |
|---|---|
| `FOR EACH i IN a -> b` with `a` greater than `b` | error |
| One `WHILE` or `FOR` loop may run at most 1,000,000 times | run time |
| Function calls may nest at most 100 deep | run time |

### Functions

| Rule | Kind |
|---|---|
| A function must `RETURN` a value | error |
| A function sees its parameters, its own locals, the employee handles, and the built-ins `employees` and `company` (`company` only if `COMPANY` came before the function). Global variables are not visible inside a function | error |
| A function must be declared before it is called, with the right number of arguments | error |

### Arrays

| Rule | Kind |
|---|---|
| Arrays are 1-based | behaviour |
| Arrays are copied on `SET`, when passed to a function, and into a `FOR EACH` variable, so changing a copy never changes the original | behaviour |

### Types and numbers

| Rule | Kind |
|---|---|
| `text + text` joins; `text + number` is an error | run time |
| Division by zero | run time |
| Whole numbers are ints; fractions are exact decimals, so `0.1 + 0.2 = 0.3` | behaviour |

### Built-in functions

| Function | Behaviour |
|---|---|
| `INPUT()` or `INPUT(prompt)` | Reads one line from standard input. A value that looks like a number becomes a number, otherwise it stays text. Running out of input is a run-time error |
| `LENGTH(x)` | Number of items in an array, or characters in a text. Exactly one argument |