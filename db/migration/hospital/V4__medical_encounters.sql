CREATE TABLE medical_encounters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_number varchar(40) NOT NULL UNIQUE CHECK (btrim(encounter_number) <> ''),
    patient_id uuid NOT NULL REFERENCES patients(id),
    doctor_id uuid REFERENCES doctors(id),
    status varchar(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'arrived', 'in_progress', 'completed', 'cancelled', 'entered_in_error')),
    scheduled_at timestamptz,
    started_at timestamptz,
    ended_at timestamptz,
    chief_complaint text,
    cancellation_reason text,
    correction_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)),
    CHECK (status <> 'completed' OR (doctor_id IS NOT NULL AND ended_at IS NOT NULL)),
    CHECK (status <> 'in_progress' OR (doctor_id IS NOT NULL AND started_at IS NOT NULL)),
    CHECK (status <> 'cancelled' OR NULLIF(btrim(cancellation_reason), '') IS NOT NULL),
    UNIQUE (id, patient_id)
);

CREATE TABLE vital_signs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    measured_at timestamptz NOT NULL DEFAULT now(),
    recorded_by_user_id uuid,
    temperature_c numeric(5,2) CHECK (temperature_c > -273.15),
    systolic_bp_mmhg numeric(6,2) CHECK (systolic_bp_mmhg >= 0),
    diastolic_bp_mmhg numeric(6,2) CHECK (diastolic_bp_mmhg >= 0),
    heart_rate_bpm numeric(6,2) CHECK (heart_rate_bpm >= 0),
    respiratory_rate_per_min numeric(6,2) CHECK (respiratory_rate_per_min >= 0),
    oxygen_saturation_pct numeric(5,2) CHECK (oxygen_saturation_pct BETWEEN 0 AND 100),
    weight_kg numeric(8,3) CHECK (weight_kg >= 0),
    height_cm numeric(7,2) CHECK (height_cm >= 0),
    status varchar(20) NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'corrected', 'entered_in_error')),
    correction_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(temperature_c, systolic_bp_mmhg, diastolic_bp_mmhg,
        heart_rate_bpm, respiratory_rate_per_min, oxygen_saturation_pct, weight_kg, height_cm) > 0)
);

CREATE TABLE clinical_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    author_doctor_id uuid NOT NULL REFERENCES doctors(id),
    note_type varchar(30) NOT NULL CHECK (note_type IN ('assessment', 'progress', 'procedure', 'addendum')),
    content text NOT NULL CHECK (btrim(content) <> ''),
    status varchar(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'signed', 'entered_in_error')),
    signed_at timestamptz,
    correction_reason text,
    amends_note_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, encounter_id),
    FOREIGN KEY (amends_note_id, encounter_id) REFERENCES clinical_notes(id, encounter_id),
    CHECK (amends_note_id IS NULL OR amends_note_id <> id),
    CHECK (status <> 'signed' OR signed_at IS NOT NULL),
    CHECK (signed_at IS NULL OR status IN ('signed', 'entered_in_error')),
    CHECK (signed_at >= created_at)
);

CREATE TABLE encounter_status_histories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    from_status varchar(20) CHECK (from_status IN
        ('scheduled', 'arrived', 'in_progress', 'completed', 'cancelled', 'entered_in_error')),
    to_status varchar(20) NOT NULL CHECK (to_status IN
        ('scheduled', 'arrived', 'in_progress', 'completed', 'cancelled', 'entered_in_error')),
    actor_user_id uuid,
    reason text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CHECK (from_status IS DISTINCT FROM to_status)
);

CREATE TABLE follow_up_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    responsible_doctor_id uuid REFERENCES doctors(id),
    recommendation text NOT NULL CHECK (btrim(recommendation) <> ''),
    due_on date CHECK (isfinite(due_on)),
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'cancelled')),
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'completed') = (completed_at IS NOT NULL)),
    CHECK (completed_at >= created_at)
);
