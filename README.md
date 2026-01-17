# 💰 Bill Splitter Pro

A smart bill splitting application that uses AI to extract items from grocery bills and calculate who owes what.

## Features

- 📸 Upload bill images (JPG, PNG)
- 🤖 AI-powered item extraction using Claude Haiku
- 👥 Easy participant selection with checkboxes
- 💶 Automatic split calculations
- 📱 WhatsApp-ready summary for groups

## Tech Stack

- Python 3.12
- Streamlit (Web UI)
- Claude AI (Anthropic API)
- PIL (Image processing)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/bill-splitter.git
cd bill-splitter
```

2. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your-api-key-here
```

5. Run the app:
```bash
streamlit run app.py
```

## Usage

1. Upload your grocery bill images
2. AI extracts all items automatically
3. Select who used each item with checkboxes
4. Choose who paid each bill
5. Get detailed settlement summary
6. Copy and share with your group!

## Author

Lakshmikanth Vemuri
