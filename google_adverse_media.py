import os
import requests
from dotenv import load_dotenv
from newspaper import Article
from fake_useragent import UserAgent
from googletrans import Translator
from openpyxl import Workbook
from openpyxl.styles import Alignment
from transformers import AutoModelWithLMHead, AutoTokenizer
from nltk.tokenize import sent_tokenize
load_dotenv()

# Type in your search query target and adverse media strings
TARGET = "petropavlovsk"
ADVERSE_STRINGS = "AND court OR launder OR fraud OR bribe OR corrupt"

API_KEY = os.getenv("API_KEY")
SEARCH_ID = os.getenv("SEARCH_ID")
URL = "https://www.googleapis.com/customsearch/v1"

# set the search parameters
params = {
    "q": TARGET + " " + ADVERSE_STRINGS, 
    "key": API_KEY,
    "cx": SEARCH_ID,
    "num": 5
}

# Create a new Excel workbook
EXCEL_PATH = 'Adverse_media_summary.xlsx'
wb = Workbook()
ws = wb.active

# Create header row
header = ['URL', 'Summary']
ws.append(header)

# Set alignment for the entire 'B' column
column = ws.column_dimensions['B']
column.width = 50  # Set column width
column.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

# function that splits text in order to fit googletranslate's limit
def split_text(text, max_length=4999):
    # Check if the text exceeds the max length
    if len(text) <= max_length:
        return [text]

    # Tokenize the text into sentences
    sentences = sent_tokenize(text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # Check if adding the current sentence exceeds the max length
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence + ' '
        else:
            # Add the current chunk to the list and start a new chunk
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ' '

    # Add the last chunk to the list
    chunks.append(current_chunk.strip())

    return chunks

# Use a random User-Agent
try:
    user_agent = UserAgent()
    headers = {
    "User-Agent": user_agent.random  
}
    response = requests.get(URL, params=params, timeout=20)
    
    if response.status_code == 200:
        search_results = response.json().get("items", [])
        
        for result in search_results:
            link = result.get('link', '')

            if link:
                article = Article(link, headers=headers)
                article.download()
                article.parse()
                article.nlp()

                # Split the text into chunks
                text_chunks = split_text(article.text)

                # Translate the title and the text chunks
                translator = Translator()

                print("========================= \n=========================")

                # Combine the translated chunks
                translated_text = ""
                for i, chunk in enumerate(text_chunks, start=1):
                    # Translate each chunk separately
                    chunk_translation = translator.translate(chunk).text
                    translated_text += chunk_translation + ' '

                print("Article Text:", translated_text.strip())
                print("========================= \n=========================")
                print(f"Keywords:  {article.keywords}")

                # Hugging Face summarization model
                tokenizer = AutoTokenizer.from_pretrained("mrm8488/t5-base-finetuned-summarize-news")
                model = AutoModelWithLMHead.from_pretrained("mrm8488/t5-base-finetuned-summarize-news")


                # Hugging Face summarization module
                def summarize(text, max_length=400):
                    input_ids = tokenizer.encode(text, return_tensors="pt", add_special_tokens=True)

                    generated_ids = model.generate(
                        input_ids=input_ids, num_beams=4, max_length=max_length,  
                        repetition_penalty=2.5, length_penalty=1.0, early_stopping=True
                        )

                    preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=True) for g in generated_ids]

                    return preds[0]
                
                summary = summarize(translated_text, 400)

                # append the urls and summaries to excel
                data = [link, summary]
                ws.append(data)
                
                wb.save(EXCEL_PATH)

    else:
        print(f"Request failed with status code: {response.status_code} Response content: {response.text}")

except requests.Timeout:
    print("Request timed out")

except requests.RequestException as e:
    print(f"Request failed with exception: {e}")



