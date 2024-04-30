
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

with open(".gitignore") as f:
    exclude_patterns = [line.strip() for line in f.readlines()]

extensions = [
    "sphinx.ext.autodoc",
]
