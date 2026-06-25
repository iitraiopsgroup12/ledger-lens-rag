## Role

You are a senior Python/FastAPI + LangChain/LangGraph engineer extending the
**LedgerLens RAG** service. Add a new **`/kpi` conversational endpoint** backed by
an **agentic workflow** that, given a natural-language request and a user's email,
identifies the company, enforces an access-scope guardrail, fetches and parses the
company's filing, and generates a **structured KPI JSON** using the project's
existing LLM stack. The workflow is **stateful per user** (chat memory keyed by
email) and supports **human-in-the-loop (HITL) approval** before the final KPI
generation.

Requirements: 
1. There will be new rest endpoint with /kpi responsible to performa analysis of different KPI  
2. The /kpi chat will accept the user email, Company Symbol, Chat Message as KPI Query.
3. The /kpi should save the history of chat 
4. The /kpi also will have Human-in-the-loop approval capability to suggest user further to add more KPI 
3. The /kpi will make call to KPIServie to initiate the Agentic Workflow which involved the following sequence

Access Provided:
1.  There is existing PostgreSQL hosted on local host, The tables list available in /docs/db.sql
2.  List of financial document can be access from with help of nsc_data_storage LocalFileStorage class retrieve() method passing the storage id
3.  The Storage will be retrieve from documents table from db and with column name s3_key. 
4.  If the s3_kay  value start with "file://" the LocalFileStorage class should be use 
5.  If the s3_kay  value start with "aws://" the AwsFileStorage class should be use 

Agentic AI Workflow: Tobe initiated from KPIServie
1.  The Agentic AI with start with Guardrail that check if Chat Message is related to finance domain else agentic workflow return appropriated response 
2.  The Workflow start with accepting the Company Symbol, Read the Values from companies db table. Agent should move to next step if company row found.
3.  The Next step to check the email address provided if the is available with this email. Agent should move to next step if User row found.
4.  The Next Step is check in database if user and companies are mapped based on the relationship available in db table watchlist. Agent should move to next step if mapping row found.
5.  The Next Step is to get information about all document location related to company fetch from database. Fetch all the rows from documents  table with company_id. Agent should move to next step if documents found.
6.  The Next Step is to get s3_key from document table, Get document from Storage DataStorage implementation, Parse the document based on the default parser available in the existing api. and preprocess to get textual content.
8.  The Next step is with the help of llm, validate the parsed document against the KPI duration that user ask in chat message.  
9.  The next step is  the agent will design the prompt to generate the formated JSON output of KPI. The possible list of KPI user can ask is available in KPI-List.txt in Categories The prompt for the KPI available in /docs/kpi-prompt.ml
10. Next the Agentic work flow will make a call to LLM with the documents that are available in llm.py and generate the response 

Nots: Consider the existing application and langchain framework to implement Agentic API Workflow

The /KPI should maintain the separate session based on the email of user to store the history and Human-in-the-loop approval.

