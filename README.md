## IoT Delta Robot

### Running the code

**Prerequisites:** Python 3.8+

```bash
python -m venv .venv

source .venv/bin/activate   # for MacOS/Linux

.venv\Scripts\activate      # for Windows

pip install -r requirements.txt
```

**Run the FastAPI server:**
```bash
# From the project root directory
uvicorn main.main:app --reload
```

**Access the web UI:**
Open your browser and navigate to `http://localhost:8000`
