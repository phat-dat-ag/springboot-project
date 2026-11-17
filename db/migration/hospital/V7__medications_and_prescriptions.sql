CREATE TABLE medication_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(40) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_medication_category_active_code ON medication_categories(code)
    WHERE deleted_at IS NULL;

CREATE TABLE medications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES medication_categories(id),
    code varchar(60) NOT NULL CHECK (btrim(code) <> ''),
    generic_name varchar(200) NOT NULL CHECK (btrim(generic_name) <> ''),
    brand_name varchar(200),
    dosage_form varchar(80) NOT NULL CHECK (btrim(dosage_form) <> ''),
    strength varchar(100) NOT NULL CHECK (btrim(strength) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_medication_active_code ON medications(code) WHERE deleted_at IS NULL;

CREATE TABLE prescriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_number varchar(40) NOT NULL UNIQUE CHECK (btrim(prescription_number) <> ''),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    prescribing_doctor_id uuid NOT NULL REFERENCES doctors(id),
    status varchar(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'signed', 'cancelled', 'superseded', 'entered_in_error')),
    signed_at timestamptz,
    supersedes_prescription_id uuid,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, encounter_id),
    UNIQUE (supersedes_prescription_id),
    FOREIGN KEY (supersedes_prescription_id, encounter_id) REFERENCES prescriptions(id, encounter_id),
    CHECK (supersedes_prescription_id IS NULL OR supersedes_prescription_id <> id),
    CHECK (status <> 'signed' OR signed_at IS NOT NULL),
    CHECK (signed_at IS NULL OR status IN ('signed', 'cancelled', 'superseded', 'entered_in_error')),
    CHECK (signed_at >= created_at),
    CHECK (status NOT IN ('cancelled', 'superseded', 'entered_in_error')
        OR NULLIF(btrim(reason), '') IS NOT NULL)
);

CREATE TABLE prescription_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id uuid NOT NULL REFERENCES prescriptions(id),
    medication_id uuid NOT NULL REFERENCES medications(id),
    item_number integer NOT NULL CHECK (item_number > 0),
    dosage text NOT NULL CHECK (btrim(dosage) <> ''),
    administration_route varchar(80) NOT NULL CHECK (btrim(administration_route) <> ''),
    frequency text NOT NULL CHECK (btrim(frequency) <> ''),
    duration_days integer CHECK (duration_days > 0),
    starts_on date CHECK (isfinite(starts_on)),
    ends_on date CHECK (isfinite(ends_on)),
    quantity numeric(12,3) NOT NULL CHECK (quantity > 0),
    quantity_unit varchar(40) NOT NULL CHECK (btrim(quantity_unit) <> ''),
    instructions text,
    as_needed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (prescription_id, item_number),
    CHECK (ends_on >= starts_on)
);

CREATE TABLE prescription_histories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id uuid NOT NULL REFERENCES prescriptions(id),
    from_status varchar(20) CHECK (from_status IN
        ('draft', 'signed', 'cancelled', 'superseded', 'entered_in_error')),
    to_status varchar(20) NOT NULL CHECK (to_status IN
        ('draft', 'signed', 'cancelled', 'superseded', 'entered_in_error')),
    actor_user_id uuid,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CHECK (from_status IS DISTINCT FROM to_status)
);
