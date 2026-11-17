CREATE TABLE doctors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id uuid UNIQUE,
    license_authority varchar(100) NOT NULL CHECK (btrim(license_authority) <> ''),
    license_number varchar(80) NOT NULL CHECK (btrim(license_number) <> ''),
    given_name varchar(100) NOT NULL CHECK (btrim(given_name) <> ''),
    family_name varchar(100),
    license_expires_on date CHECK (isfinite(license_expires_on)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (license_authority, license_number)
);

CREATE TABLE specialties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(40) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_specialties_active_code ON specialties(code) WHERE deleted_at IS NULL;

CREATE TABLE doctor_specialties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id uuid NOT NULL REFERENCES doctors(id),
    specialty_id uuid NOT NULL REFERENCES specialties(id),
    is_primary boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (doctor_id, specialty_id),
    CHECK (NOT is_primary OR is_active)
);
CREATE UNIQUE INDEX uq_doctor_primary_specialty ON doctor_specialties(doctor_id) WHERE is_primary;
