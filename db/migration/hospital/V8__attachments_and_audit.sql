CREATE TABLE medical_attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patients(id),
    encounter_id uuid,
    uploaded_by_user_id uuid NOT NULL,
    file_name varchar(255) NOT NULL CHECK (btrim(file_name) <> ''),
    media_type varchar(127) NOT NULL CHECK (btrim(media_type) <> ''),
    storage_provider varchar(40) NOT NULL CHECK (btrim(storage_provider) <> ''),
    storage_key text NOT NULL CHECK (btrim(storage_key) <> ''),
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    sha256_hex varchar(64) CHECK (sha256_hex ~ '^[0-9a-f]{64}$'),
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    FOREIGN KEY (encounter_id, patient_id) REFERENCES medical_encounters(id, patient_id),
    UNIQUE (storage_provider, storage_key)
);

-- Deliberately no payload/before/after JSON: audit identifiers and controlled codes only.
CREATE TABLE clinical_audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid REFERENCES patients(id),
    actor_user_id uuid,
    actor_type varchar(20) NOT NULL CHECK (actor_type IN ('user', 'service', 'system')),
    operation varchar(20) NOT NULL CHECK (operation IN
        ('create', 'update', 'sign', 'cancel', 'correct', 'supersede', 'soft_delete')),
    entity_type varchar(60) NOT NULL CHECK (btrim(entity_type) <> ''),
    entity_id uuid NOT NULL,
    reason_code varchar(60) CHECK (reason_code ~ '^[a-z0-9_]+$'),
    correlation_id uuid,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CHECK (actor_type <> 'user' OR actor_user_id IS NOT NULL)
);

CREATE TABLE medical_record_access_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patients(id),
    actor_user_id uuid,
    actor_type varchar(20) NOT NULL CHECK (actor_type IN ('user', 'service', 'system')),
    operation varchar(20) NOT NULL CHECK (operation IN ('view', 'search', 'download', 'export')),
    entity_type varchar(60),
    entity_id uuid,
    purpose_code varchar(60) NOT NULL CHECK (purpose_code ~ '^[a-z0-9_]+$'),
    outcome varchar(20) NOT NULL CHECK (outcome IN ('allowed', 'denied', 'failed')),
    correlation_id uuid,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((entity_type IS NULL) = (entity_id IS NULL)),
    CHECK (actor_type <> 'user' OR actor_user_id IS NOT NULL)
);
