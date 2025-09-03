# CodeGreen Documentation

This directory contains the documentation website for CodeGreen, built with MkDocs Material.

## Structure

```
docs/
├── README.md                 # This file
└── website/                  # MkDocs website
    ├── mkdocs.yml           # MkDocs configuration
    ├── dev-server.sh        # Development server script
    ├── gen_ref_pages.py     # API reference generator
    └── docs/                # Documentation source files
        ├── index.md         # Homepage
        ├── getting-started/ # Getting started guides
        ├── user-guide/      # User documentation
        ├── api/             # API reference
        ├── examples/        # Usage examples
        ├── development/     # Development guides
        └── about/           # About and legal
```

## Development

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Install dependencies:
   ```bash
   pip install mkdocs mkdocs-material mkdocstrings[python]
   ```

2. Start development server:
   ```bash
   cd docs/website
   ./dev-server.sh
   ```

   Or manually:
   ```bash
   cd docs/website
   mkdocs serve
   ```

### Building

Build the documentation:

```bash
cd docs/website
mkdocs build
```

The built site will be in `docs/website/site/`.

## Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch.

### Manual Deployment

To deploy manually:

```bash
cd docs/website
mkdocs gh-deploy
```

## Adding Content

1. **New Pages**: Add markdown files to the appropriate directory in `docs/website/docs/`
2. **Navigation**: Update `mkdocs.yml` to include new pages in the navigation
3. **API Reference**: Use mkdocstrings syntax to include Python docstrings:

   ```markdown
   # API Reference
   
   ::: codegreen.core.engine
   ```

## Customization

- **Theme**: Configured in `mkdocs.yml` under the `theme` section
- **Plugins**: Add new plugins in the `plugins` section
- **Extensions**: Configure markdown extensions in `markdown_extensions`

## Contributing

1. Make changes to documentation files
2. Test locally with `mkdocs serve`
3. Submit a pull request
4. Documentation will be automatically deployed on merge