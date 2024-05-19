
html_title = "Ember"
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "sticky_navigation": False,
    "collapse_navigation": False,
    "navigation_depth": 3,
    "logo_only": True,
}
html_logo = "_static/embr-rv32-600.png"

with open(".gitignore") as f:
    exclude_patterns = [line.strip() for line in f.readlines()]

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]
autodoc_member_order = "bysource"

napoleon_numpy_docstring = True
napoleon_custom_sections = [
    ("Ports", "params_style"),
    ("Values", "params_style"),
    ("Fields", "params_style"),
    ("Members", "params_style"),
]

rst_prolog = """
"""
