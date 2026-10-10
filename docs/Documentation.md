# Documentation

## EBNF:

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

KEYWORDS         = COMPANY EMPLOYEE END TAX BELOW ABOVE
                   ADD EXEMPT CONTRIBUTE LESS PAYSLIP PRINT
                   SET TO IF THEN ELSE WHILE FOR EACH IN
                   FUNCTION RETURN INPUT LENGTH
                   AND OR NOT TRUE FALSE ;   (* uppercase only *)

(* ================= VALIDATOR RULES (not grammar) ================= *)
(* COMPANY: exactly one; working_days and hours_per_day required     *)
(* EMPLOYEE: name and salary required; unknown fields are errors      *)
(* Reserved names: employees, company, all computed fields            *)
(* Computed fields are read-only (SET net TO ... is an error)         *)
(* Labels: case-sensitive; duplicate per employee is a run-time error;        *)
(*   labels differing only in case give a warning                     *)
(* Reserved labels: "Basic Pay" "Absences" "Tardiness" "Overtime"     *)
(*   "Withholding Tax"                                                *)
(* Overtime: overtime_hours * hourly_rate * 1.25 is added to gross    *)
(*   and taxable automatically; shown as an "Overtime" payslip row    *)
(*   when greater than 0. Do not ADD overtime by hand.                *)
(* TAX rows: overlapping ranges are an error                          *)
(* TAX gaps: income between two rows (fractions included) is an       *)
(*   error; a table with no ABOVE row only warns. Income below the    *)
(*   first row is untaxed.                                            *)
(* TAX rate: a row's % applies to (income - the row's own lower       *)
(*   bound), plus its fixed amount; a BELOW row counts from 0.        *)
(* FOR ranges: start > end (e.g. 3 -> 1) is an error                  *)
(* Arrays are 1-based; loop variable cannot shadow an employee handle *)
(* Arrays are copied on SET, when passed to a function, and into a    *)
(*   FOR EACH variable; changing a copy never changes the original.   *)
(* Loops: one WHILE or FOR may run at most 1,000,000 times (run-time  *)
(*   error), which stops accidental infinite loops.                   *)
(* Declarations (COMPANY EMPLOYEE TAX FUNCTION) are top-level only    *)
(* Everything runs top to bottom; declare before use                  *)
(* TAX: at most one block; more than one is an error                  *)
(* Pay targets: a declared handle or a FOR EACH loop variable         *)
(* Duplicate labels: caught at run time, so IF branches may repeat    *)
(* Functions: no pay commands inside; RETURN is required              *)
(* Function scope: sees its parameters, its own locals, employee      *)
(*   handles, and the built-ins employees and company (company only   *)
(*   if COMPANY came before the function). Global variables are not   *)
(*   visible inside a function.                                       *)
(* Types: text + text joins; text + number is an error; divide by 0 is an error *)
(* Numbers: whole numbers are ints, fractions are exact decimals      *)
(*   (0.1 + 0.2 = 0.3). Pay amounts, absences, tardiness, overtime    *)
(*   and tax are each rounded to centavos (halves up) when computed,  *)
(*   so payslip rows always add up to Gross and Net.                  *)