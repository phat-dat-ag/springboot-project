
-- Add clinical conclusion to medical encounters.
-- Nullable field; nonblank values are required.

ALTER TABLE public.medical_encounters
    ADD COLUMN clinical_conclusion VARCHAR(4000);

ALTER TABLE public.medical_encounters
    ADD CONSTRAINT chk_medical_encounters_clinical_conclusion_not_blank
    CHECK (
        clinical_conclusion IS NULL
        OR BTRIM(clinical_conclusion) <> ''
    );
