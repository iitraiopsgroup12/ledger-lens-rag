
Create Detail prompt draft in markdown in /docs, to create Agentic AI Workflow With the following requirement
to create API 

1. There will be new rest endpoint with /kpi responsible to performa analysis of different KPI defined  in the file 
2. The /kpi chat will accept the user email to maintain chat memory also additional file upload as optional if user
   wants to include this file during KPI generation.
3. The /kpi will make call to KPIServie to initiate the Agentic Workflow which involved the following sequence
   3.1 The agentic workflow first analyse the prompt text to identify the company name of its company symbol. 
       for this analysis the workflow make call to database table companies, watchlist and the user. the SQL table 
       defination available in /docs/db.sql
       if user email is not attached to company as mapping is available in watchlist the agent will stop and 
       response back to the use "The Analysis of this company is not in your scope" as guardrails part.
   3.2 if email is attached to the company the next stop of agentic workflow to get the document of the company 
       The documents information for the company is available in DB table documents, annual_report and financial_results.
       Check all the fields of this table as use can ask about KPI in natural language.
       the value from DB related to the company and the location of document is available in s3_ksy
   3.4 The Next is based on the s3_key, if Key is not the agentic workflow will get the document with the help of package 
       nsc_data_storage default implementation of DataStorage retrieve() method
   3.5 The Next Agent will parse the document based on the default parser available in the existing api. and preprocess
       to get textual content. 
   4.5 Next agent will design the prompt to generate the formated JSON output of KPI.
   4.6 Next the Agentic work flow will make a call to LLM that are available in llm.py and generate the response.

4. The possible list of KPI user can ask is available in KPI-List.txt in Categories 
5. The prompt for the KPI available in /docs/kpi-prompt.ml

Nots: Consider the existing application and langchain framework to implement Agentic API Workflow
the /kpi should same the history of chat also will have Human-in-the-loop approval capability. 
The /KPI should maintain the saperate session based on the email of user to store the history and Human-in-the-loop approval.

