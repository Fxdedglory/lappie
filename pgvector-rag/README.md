Book RAG – Fundamentals of Data Engineering (version_2)

- Uses chat_ingest database (bronze.web_docs + vector.doc_chunks)
- Uses Ollama (nomic-embed-text for embeddings, llama3.2 for chat)
- Entrypoints:
  - python .\app\insert_book_pdf.py   # ingest/update book
  - python .\app\search_book_faq.py   # ask questions about the book
