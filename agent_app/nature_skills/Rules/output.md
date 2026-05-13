# Output Directory Rules

## 1. Output Location
All generated artifacts, including:
- Images (.png, .jpg, .svg)
- Data files (.csv, .xlsx)
- Reports (.pdf, .md)

MUST be saved to the following absolute path:
`d:\Code\python\Mathematical Modeling\output`

## 2. Forbidden Locations
Do NOT save generated files to:
- `Explorer_Draw\Knowledge Base`
- `problem\model` (the source directory)
- `problem\data` (the input directory)

## 3. Implementation Requirements
All Python scripts generating output MUST include the following logic to ensure the output directory exists:

```python
import os

OUTPUT_DIR = r'd:\Code\python\Mathematical Modeling\output'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
```

## 5. Documentation Requirement (Mandatory)
For every visualization generated, you MUST **APPEND** the explanation to the central log file:
`d:\Code\python\Mathematical Modeling\output\figure_Explanation.txt`

**Content Requirements:**
1.  **Filenames**: List the generated image files.
2.  **Meanings**: Explain the scientific meaning and key insights of each figure/panel.
3.  **LaTeX Citation**: Provide a complete `\begin{figure} ... \end{figure}` block including:
    *   Correct file paths (e.g., `output/filename.png`).
    *   `\caption{}` with bolded titles and detailed descriptions.
    *   `\label{}` for referencing.
4.  **Usage Examples**: Show how to cite the figure in the text (e.g., "As shown in Figure \ref{...}...").

**Implementation Note:**
- Do NOT overwrite the file. Always use append mode (`'a'`).
- Ensure `utf-8` encoding.
- Add a separator (e.g., `\n\n=========================================\n\n`) between entries.

**Example Structure:**
```text
1. Figure Files
   - Fig_A.png
2. Meaning
   - Fig A shows the correlation between X and Y...
3. LaTeX Code
   \begin{figure}
     \includegraphics{output/Fig_A.png}
     \caption{...}
   \end{figure}
```
