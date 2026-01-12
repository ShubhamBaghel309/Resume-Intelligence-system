# Common Setup Issues & Solutions

## Issue 1: "ModuleNotFoundError: No module named 'app'"

### Error Message:
```
ModuleNotFoundError: No module named 'app'
```

### Cause:
The script is being run from the wrong directory, or Python can't find the project modules.

### Solution:

**Option A: Run from Project Root (Easiest)**
```bash
# Navigate to project root first
cd Resume-Intelligence-system-main

# Verify you're in the right place (should see 'app' folder)
dir  # Windows
ls   # Mac/Linux

# Then run the script
python scripts\test_agent.py
```

**Option B: The script has been fixed!**
The `test_agent.py` script now automatically finds the project root, so it should work from any directory.

---

## Issue 2: "No module named 'langchain_groq'" or similar

### Error Message:
```
ModuleNotFoundError: No module named 'langchain_groq'
```

### Solution:
Install missing dependencies:

```bash
# Install all requirements
pip install -r requirements.txt

# Or install specific missing package
pip install langchain-groq
```

---

## Issue 3: "GROQ_API_KEY not found"

### Error Message:
```
ValueError: GROQ_API_KEY not found in environment variables
```

### Solution:

1. **Create `.env` file** in project root:
   ```
   GROQ_API_KEY=your_actual_api_key_here
   ```

2. **Get API key** from https://console.groq.com/

3. **Verify `.env` location**:
   ```
   Resume-Intelligence-system-main/
   ├── .env          ← Should be here
   ├── app/
   ├── scripts/
   └── requirements.txt
   ```

---

## Issue 4: Database Connection Errors

### Error Message:
```
sqlite3.OperationalError: unable to open database file
```

### Solution:

**Check database path:**
```bash
# The database should be at project root
Resume-Intelligence-system-main/
└── resumes.db    ← Should be here
```

**If missing, run setup:**
```bash
python scripts/reset_database.py
python scripts/process_all_resumes.py
```

---

## Issue 5: ChromaDB Errors

### Error Message:
```
chromadb.errors.InvalidDimensionException
```

### Solution:

**Reset ChromaDB:**
```bash
# Delete ChromaDB storage
rm -rf storage/chroma  # Mac/Linux
Remove-Item -Recurse -Force storage\chroma  # Windows

# Re-index resumes
python scripts/reindex_with_new_chunks.py
```

---

## Issue 6: Python Version Issues

### Error Message:
```
SyntaxError: invalid syntax
```

### Solution:

**Check Python version:**
```bash
python --version
```

**Required: Python 3.9 or higher**

If version is too old:
- Download from https://www.python.org/downloads/
- Install Python 3.11 (recommended)

---

## Issue 7: Virtual Environment Issues

### Problem:
Packages installed but still getting import errors

### Solution:

**Activate virtual environment:**

```bash
# Windows
myenv\Scripts\activate

# Mac/Linux
source myenv/bin/activate

# Verify activation (should show (myenv) in prompt)
```

**Or create new virtual environment:**
```bash
# Create new venv
python -m venv myenv

# Activate it
myenv\Scripts\activate  # Windows
source myenv/bin/activate  # Mac/Linux

# Install requirements
pip install -r requirements.txt
```

---

## Complete Fresh Setup Checklist

For someone setting up the project for the first time:

### 1. Prerequisites
- ✅ Python 3.9+ installed
- ✅ Git installed (optional)
- ✅ Groq API key obtained

### 2. Download Project
```bash
# If using Git
git clone <repository-url>
cd Resume-Intelligence-system-main

# Or download ZIP and extract
```

### 3. Create Virtual Environment
```bash
python -m venv myenv
myenv\Scripts\activate  # Windows
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment
```bash
# Create .env file in project root
echo GROQ_API_KEY=your_key_here > .env
```

### 6. Setup Database
```bash
# Initialize database
python scripts/reset_database.py

# Add sample resumes to downloaded_pdfs/ folder
# Then process them
python scripts/process_all_resumes.py
```

### 7. Test the System
```bash
# Test the intelligent agent
python scripts/test_agent.py

# Or run specific tests
python scripts/test_hybrid_search.py
```

---

## Quick Verification Commands

**Check if everything is set up correctly:**

```bash
# 1. Check Python version
python --version  # Should be 3.9+

# 2. Check if in virtual environment
where python  # Windows - should point to myenv
which python  # Mac/Linux - should point to myenv

# 3. Check if packages installed
pip list | findstr langchain  # Windows
pip list | grep langchain     # Mac/Linux

# 4. Check if .env exists
dir .env  # Windows
ls -la .env  # Mac/Linux

# 5. Check if database exists
dir resumes.db  # Windows
ls -la resumes.db  # Mac/Linux
```

---

## Still Having Issues?

### Enable Debug Mode

Add this to the top of your script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check File Paths

Run this diagnostic:
```python
import os
import sys

print("Current directory:", os.getcwd())
print("Script location:", __file__)
print("Python path:", sys.path)
print("Project root exists:", os.path.exists("app"))
```

### Contact Support

If issues persist, provide:
1. Full error message
2. Python version (`python --version`)
3. Operating system
4. Output of `pip list`
5. Contents of `.env` (without actual API key)

---

## Platform-Specific Notes

### Windows
- Use backslashes in paths: `scripts\test_agent.py`
- Activate venv: `myenv\Scripts\activate`
- Use PowerShell or CMD

### Mac/Linux
- Use forward slashes: `scripts/test_agent.py`
- Activate venv: `source myenv/bin/activate`
- May need `python3` instead of `python`

### Common Path Issues
- **Windows**: `C:\Users\username\project\`
- **Mac**: `/Users/username/project/`
- **Linux**: `/home/username/project/`

Always use **absolute paths** or run from **project root** to avoid issues.
