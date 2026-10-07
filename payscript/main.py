from payscript.lexer import Lexer
from pathlib import Path

def main():
    sample_dir = Path(__file__).parent.parent / "samples" / "invalid"

    if not sample_dir.exists():
        print(f"Sample directory not found: {sample_dir}")
        return

    for sample_file in sorted(sample_dir.glob("*.ps")):
        print(f"\n--- Tokenizing {sample_file.name} ---")
        try:
            source = sample_file.read_text()
            lexer = Lexer(source)
            tokens = lexer.tokenize()

            for token in tokens:
                print(f"  {token.type.name:15} {token.value!r:20} Line {token.line} Col {token.col}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    main()
