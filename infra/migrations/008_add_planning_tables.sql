-- Add plans and plan_activities tables for the Parent Planning Tool

CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    child_name VARCHAR(100) NOT NULL,
    child_age VARCHAR(20) NOT NULL,
    state VARCHAR(10) NOT NULL,
    interests TEXT,
    concerns TEXT,
    duration VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_user_id ON plans(user_id);
CREATE INDEX idx_plans_user_status ON plans(user_id, status);

CREATE TABLE plan_activities (
    id SERIAL PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    indicator_id VARCHAR(100) REFERENCES indicators(standard_id),
    activity_description TEXT NOT NULL,
    section_label VARCHAR(100),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plan_activities_plan_id ON plan_activities(plan_id);
CREATE INDEX idx_plan_activities_indicator ON plan_activities(indicator_id);
