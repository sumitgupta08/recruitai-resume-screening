-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable uuid-ossp
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
