CREATE TABLE stock_ohlcv (
    date DATE NOT NULL,
    symbol VARCHAR(15) NOT NULL,
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    close DECIMAL(15, 4),
    volume BIGINT,
    PRIMARY KEY (date, symbol)
);

CREATE TABLE stock_predicted_close (
    date DATE NOT NULL,
    symbol VARCHAR(15) NOT NULL,
    close DECIMAL(15,4),
    PRIMARY KEY (date, symbol)
);

CREATE TYPE risk_level AS ENUM ('High', 'Moderate', 'Low');

CREATE TABLE users (
    -- Primary Identifier
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
    
    -- Authentication & Identity
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    
    -- Stock Recommendation Profile (Engine Inputs)
    risk_tolerance risk_level DEFAULT 'Moderate',
    
    -- Audit & Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE TABLE questions (
    question_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_string TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL, 
    question_id_cfa VARCHAR(50) NOT NULL,
    question_category VARCHAR(50) NOT NULL,
    question_options JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE questionnaires (
    questionnaire_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    fk_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, 
    
    assessed_risk risk_level,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE question_responses (
    fk_questionnaire_id UUID NOT NULL REFERENCES questionnaires(questionnaire_id) ON DELETE CASCADE,
    fk_question_id UUID NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    
    question_response TEXT NOT NULL,
    score_received INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fk_questionnaire_id, fk_question_id)
);
