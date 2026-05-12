# Mini-C Compiler

Mini-C Compiler is a simplified educational compiler developed for a subset of the C programming language. The project demonstrates the major phases of compiler construction including lexical analysis, parsing, semantic analysis, symbol table management, Abstract Syntax Tree (AST) generation, and Three Address Code (TAC) generation.

The compiler is implemented in Python and is designed to understand how compilers work internally in a simplified and practical way. Mini-C supports essential programming constructs such as variables, arithmetic operations, loops, conditionals, arrays, and block scoping while intentionally excluding advanced C features like pointers, functions, and preprocessing directives to keep the implementation easier to understand.

The project is intended for:

- Compiler Design learning
- Academic project
- Understanding parsing and semantic analysis
- Intermediate code generation study
- Educational demonstrations

---

# How to Run the Mini-C Compiler

Follow these steps to run the compiler on your system.

---

## Step 1 — Install Python

Make sure Python 3.10 or higher is installed.

Check Python version:

```bash
python3 --version
```

Example output:

```text
Python 3.11.5
```

If Python is not installed, download it from:

https://www.python.org/downloads/

---

## Step 2 — Download or Clone the Project

### Using Git

```bash
git clone https://github.com/your-username/mini-c-compiler.git
```

Go into the project folder:

```bash
cd mini-c-compiler
```

---

## Step 3 — Verify Project Files

Make sure these files exist:

```text
mini-c-compiler/
│
├── lexer.py
├── parser.py
├── semantic.py
├── ir_gen.py
├── errors.py
├── main.py
│
├── test_program.mc
│
└── README.md
```

---

## Step 4 — Create a Mini-C Source File

Create a file named:

```text
test_program.mc
```

Example program:

```c
int x = 5;
float y = 2.5;

float z = x + y;

if (z > 5) {
    printf(z);
}

for (int i = 0; i < 3; i++) {
    x++;
}

printf(x);
```

---

## Step 5 — Run the Compiler

### Basic Run

```bash
python3 main.py test_program.mc
```

### Output

You will get:

- Tokens
- Symbol Table
- TAC (Three Address Code)

---

# Command Line Options

| Command | What You Get |
|---|---|
| `python3 main.py test_program.mc` | Tokens + Symbol Table + TAC |
| `python3 main.py test_program.mc --ast` | Above + full AST tree |
| `python3 main.py test_program.mc --quads` | Above + raw quadruple table |
| `python3 main.py test_program.mc --ast --quads` | Everything together |

---

# Example Commands

## 1. Run Normal Compilation

```bash
python3 main.py test_program.mc
```

### Output Includes

- Tokens
- Symbol Table
- TAC

---

## 2. Generate AST Tree

```bash
python3 main.py test_program.mc --ast
```

### Output Includes

- Tokens
- Symbol Table
- TAC
- AST Tree

---

## 3. Generate Quadruple Table

```bash
python3 main.py test_program.mc --quads
```

### Output Includes

- Tokens
- Symbol Table
- TAC
- Quadruple Table

---

## 4. Generate Everything

```bash
python3 main.py test_program.mc --ast --quads
```

### Output Includes

- Tokens
- Symbol Table
- AST Tree
- TAC
- Quadruple Table

---

# Example Output

## Example TAC

```text
t0 = x + y
z = t0

ifFalse z > 5 goto L0
printf z
L0:

i = 0
L1:
ifFalse i < 3 goto L2

x = x + 1

i = i + 1
goto L1

L2:
printf x
```

---

# Running Your Own Programs

You can replace:

```text
test_program.mc
```

with any Mini-C source file.

Example:

```bash
python3 main.py my_program.mc --ast --quads
```

---

# Common Errors

## File Not Found

```text
Error: file not found
```

### Solution

Make sure the `.mc` file exists inside the project folder.

---

## Python Not Installed

```text
python3: command not found
```

### Solution

Install Python and add it to PATH.

---

# Supported File Extension

Mini-C programs use:

```text
.mc
```

Examples:

```text
program.mc
sample.mc
test.mc
```