BEGIN;

ALTER TABLE bws_ai.analyses
    ADD CONSTRAINT analyses_tenant_id_unique UNIQUE (tenant_id, id);

ALTER TABLE bws_ai.proposals
    ADD COLUMN analysis_id UUID,
    ADD CONSTRAINT proposals_analysis_unique UNIQUE (analysis_id),
    ADD CONSTRAINT proposals_analysis_same_tenant_fk
        FOREIGN KEY (tenant_id, analysis_id)
        REFERENCES bws_ai.analyses(tenant_id, id);

GRANT INSERT (analysis_id) ON bws_ai.proposals TO aegisai_app;

COMMIT;
