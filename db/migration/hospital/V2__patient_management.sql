CREATE TABLE patients (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    medical_record_number varchar(40) NOT NULL UNIQUE CHECK (btrim(medical_record_number) <> ''),
    external_user_id uuid UNIQUE,
    given_name varchar(100) NOT NULL CHECK (btrim(given_name) <> ''),
    family_name varchar(100),
    date_of_birth date,
    sex_at_birth varchar(20) CHECK (sex_at_birth IN ('female', 'male', 'intersex', 'unknown')),
    deceased_on date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (date_of_birth IS NULL OR isfinite(date_of_birth)),
    CHECK (deceased_on IS NULL OR isfinite(deceased_on)),
    CHECK (deceased_on >= date_of_birth)
);

CREATE TABLE patient_contacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patients(id),
    contact_type varchar(20) NOT NULL CHECK (contact_type IN ('self', 'emergency', 'guardian')),
    contact_name varchar(200),
    relationship varchar(100),
    phone varchar(40),
    email varchar(254),
    address_text text,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (num_nonnulls(NULLIF(btrim(phone), ''), NULLIF(btrim(email), ''),
        NULLIF(btrim(address_text), '')) > 0),
    CHECK (contact_type = 'self' OR NULLIF(btrim(contact_name), '') IS NOT NULL)
);
CREATE UNIQUE INDEX uq_patient_primary_contact ON patient_contacts(patient_id, contact_type)
    WHERE is_primary AND deleted_at IS NULL;

CREATE TABLE patient_allergies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patients(id),
    allergen text NOT NULL CHECK (btrim(allergen) <> ''),
    reaction text,
    severity varchar(20) CHECK (severity IN ('mild', 'moderate', 'severe', 'unknown')),
    status varchar(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'resolved', 'entered_in_error')),
    onset_on date CHECK (isfinite(onset_on)),
    recorded_by_user_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE patient_medical_histories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES patients(id),
    history_type varchar(20) NOT NULL
        CHECK (history_type IN ('medical', 'surgical', 'family', 'social', 'other')),
    description text NOT NULL CHECK (btrim(description) <> ''),
    started_on date CHECK (isfinite(started_on)),
    ended_on date CHECK (isfinite(ended_on)),
    status varchar(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'resolved', 'entered_in_error')),
    recorded_by_user_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_on >= started_on)
);
