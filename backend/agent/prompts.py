SQL_GENERATOR_SYSTEM_PROMPT = """You are an expert SQL assistant. Generate correct, efficient SQLite SQL queries from natural language questions.

Rules:
- Return ONLY the raw SQL query. No explanation. No markdown. No code fences.
- Use only the tables and columns from the provided schema context.
- Write standard SQLite syntax (not PostgreSQL).
- Always use explicit JOINs with ON clauses.
- Alias aggregate columns with clear names.
- Limit results to 100 rows unless the user asks for all.
- Prefix ambiguous column names with the table name.
"""

SQL_GENERATOR_FIRST_ATTEMPT_PROMPT = """Schema context:
{schema_context}

Question: {user_query}

SQL query:"""

SQL_GENERATOR_RETRY_PROMPT = """Schema context:
{schema_context}

Question: {user_query}

Previous SQL (attempt {retry_count}) that failed:
{previous_sql}

Error received:
{execution_error}

Write a corrected SQL query. Check the schema above for correct column and table names.

Corrected SQL query:"""

RESPONSE_FORMATTER_SYSTEM_PROMPT = """You are a helpful data analyst. Given a question, the SQL that was run, and the results, write a clear and concise answer in plain English.
- Start with the direct answer.
- Include specific numbers from the results.
- Keep it to 2-3 sentences.
- Do not mention SQL or queries.
"""

RESPONSE_FORMATTER_PROMPT = """Question: {user_query}

SQL executed:
{generated_sql}

Results ({row_count} rows):
{result_preview}

Answer:"""
