"""Generate API reference pages for CodeGreen documentation."""

from pathlib import Path
from mkdocs_gen_files import Nav, Plugin

nav = Nav()

# Define the modules to document
modules = [
    "codegreen",
    "codegreen.cli",
    "codegreen.core",
    "codegreen.core.config",
    "codegreen.core.engine",
    "codegreen.utils",
    "codegreen.utils.binary",
    "codegreen.utils.platform",
]

# Generate API reference pages
for module in modules:
    nav[module.split(".")] = f"{module.replace('.', '/')}.md"

# Write the navigation
with open("api/nav.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

# Generate individual module pages
for module in modules:
    module_path = module.replace(".", "/")
    with Plugin(f"{module_path}.md") as f:
        f.write(f"# {module}\n\n")
        f.write(f"::: {module}")
