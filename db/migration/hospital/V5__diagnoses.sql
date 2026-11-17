CREATE TABLE diagnosis_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    coding_system varchar(40) NOT NULL CHECK (btrim(coding_system) <> ''),
    system_version varchar(40) NOT NULL CHECK (btrim(system_version) <> ''),
    code varchar(40) NOT NULL CHECK (btrim(code) <> ''),
    description text NOT NULL CHECK (btrim(description) <> ''),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (coding_system, system_version, code)
);

CREATE TABLE encounter_diagnoses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    diagnosis_code_id uuid NOT NULL REFERENCES diagnosis_codes(id),
    diagnosing_doctor_id uuid NOT NULL REFERENCES doctors(id),
    clinical_description text,
    is_primary boolean NOT NULL DEFAULT false,
    status varchar(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'resolved', 'superseded', 'entered_in_error')),
    diagnosed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_encounter_active_primary_diagnosis ON encounter_diagnoses(encounter_id)
    WHERE is_primary AND status = 'active';
CREATE UNIQUE INDEX uq_encounter_active_diagnosis_code
    ON encounter_diagnoses(encounter_id, diagnosis_code_id) WHERE status = 'active';

CREATE TABLE diagnosis_histories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_diagnosis_id uuid NOT NULL REFERENCES encounter_diagnoses(id),
    previous_code_id uuid REFERENCES diagnosis_codes(id),
    new_code_id uuid NOT NULL REFERENCES diagnosis_codes(id),
    previous_status varchar(20) CHECK (previous_status IN
        ('active', 'resolved', 'superseded', 'entered_in_error')),
    new_status varchar(20) NOT NULL CHECK (new_status IN
        ('active', 'resolved', 'superseded', 'entered_in_error')),
    was_primary boolean,
    is_primary boolean NOT NULL,
    previous_description text,
    new_description text,
    actor_user_id uuid,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    occurred_at timestamptz NOT NULL DEFAULT now()
);
