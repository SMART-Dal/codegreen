# PyPI Authentication Setup Guide

## 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Register with email: `saurabh@dal.ca`
3. Verify your email address

## 2. Create Test PyPI Account (Optional but Recommended)

1. Go to https://test.pypi.org/account/register/
2. Register with the same email: `saurabh@dal.ca`
3. Verify your email address

## 3. Generate API Tokens

### For PyPI (Production)
1. Go to https://pypi.org/manage/account/
2. Scroll to "API tokens" section
3. Click "Add API token"
4. Token name: `codegreen-publishing`
5. Scope: "Entire account" (initially, then can scope to project later)
6. Copy the token (starts with `pypi-`)

### For Test PyPI
1. Go to https://test.pypi.org/manage/account/
2. Repeat the same process
3. Token name: `codegreen-test-publishing`
4. Copy the token (starts with `pypi-`)

## 4. Local Authentication

### Option A: Using .pypirc file
```bash
# Copy the template and update with your tokens
cp .pypirc ~/.pypirc

# Edit ~/.pypirc and replace <YOUR_PYPI_TOKEN_HERE> with actual tokens
nano ~/.pypirc

# Set proper permissions
chmod 600 ~/.pypirc
```

### Option B: Using twine directly
```bash
# For production PyPI
twine upload dist/* -u __token__ -p <your-pypi-token>

# For test PyPI
twine upload --repository testpypi dist/* -u __token__ -p <your-test-token>
```

## 5. GitHub Actions Authentication

Add these secrets to your GitHub repository:

### Repository Settings > Secrets and Variables > Actions

1. **PYPI_API_TOKEN**: Your production PyPI token
2. **TEST_PYPI_API_TOKEN**: Your test PyPI token

### How to Add Secrets:
1. Go to your GitHub repository
2. Click "Settings" tab
3. Click "Secrets and variables" > "Actions"
4. Click "New repository secret"
5. Add each token with the exact names above

## 6. Manual Publishing Process

### Step 1: Build the package
```bash
python build_wheels.py
```

### Step 2: Test on Test PyPI first
```bash
twine upload --repository testpypi dist/*
```

### Step 3: Test installation from Test PyPI
```bash
pip install -i https://test.pypi.org/simple/ codegreen
codegreen --help
```

### Step 4: Publish to Production PyPI
```bash
twine upload dist/*
```

### Step 5: Test installation from PyPI
```bash
pip install codegreen
codegreen --help
```

## 7. Automated Publishing (GitHub Actions)

The repository includes automated publishing:

### Trigger a Release:
```bash
git tag v0.1.0
git push origin v0.1.0
```

This will automatically:
1. Build wheels for Linux, macOS, Windows
2. Test the installation
3. Publish to Test PyPI
4. After validation, publish to Production PyPI

## 8. Package Name Considerations

If `codegreen` is already taken on PyPI, you may need to use:
- `codegreen-energy`
- `energy-codegreen`
- `codegreen-tool`

Check availability: https://pypi.org/project/codegreen/

## 9. First-Time Publishing Checklist

- [ ] PyPI account created with saurabh@dal.ca
- [ ] Test PyPI account created
- [ ] API tokens generated for both
- [ ] `.pypirc` configured locally
- [ ] GitHub secrets configured
- [ ] Package name availability checked
- [ ] Test build completed: `python build_wheels.py`
- [ ] Test upload to Test PyPI
- [ ] Test installation from Test PyPI
- [ ] Ready for production upload

## 10. Troubleshooting

### "Package already exists"
- Package name is taken, choose a different name
- Or you're re-uploading the same version (increment version number)

### "Invalid credentials" 
- Check token is correct and not expired
- Ensure token has the right scope (entire account or specific project)

### "File already exists"
- You're trying to upload the same version again
- Increment version number in setup.py and pyproject.toml

## Security Notes

- Never commit .pypirc file to git
- Keep API tokens secure and rotate them regularly
- Use project-scoped tokens when possible (after first upload)
- Consider using 2FA on PyPI account