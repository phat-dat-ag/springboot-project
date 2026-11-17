CREATE TABLE lab_test_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(40) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_lab_category_active_code ON lab_test_categories(code) WHERE deleted_at IS NULL;

CREATE TABLE lab_tests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL REFERENCES lab_test_categories(id),
    code varchar(60) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(200) NOT NULL CHECK (btrim(name) <> ''),
    specimen_type varchar(100),
    instructions text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_lab_test_active_code ON lab_tests(code) WHERE deleted_at IS NULL;

CREATE TABLE lab_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number varchar(40) NOT NULL UNIQUE CHECK (btrim(order_number) <> ''),
    encounter_id uuid NOT NULL REFERENCES medical_encounters(id),
    ordering_doctor_id uuid NOT NULL REFERENCES doctors(id),
    status varchar(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ordered', 'in_progress', 'completed', 'cancelled')),
    priority varchar(20) NOT NULL DEFAULT 'routine'
        CHECK (priority IN ('routine', 'urgent', 'stat')),
    ordered_at timestamptz,
    completed_at timestamptz,
    clinical_indication text,
    cancellation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status NOT IN ('ordered', 'in_progress', 'completed') OR ordered_at IS NOT NULL),
    CHECK ((status = 'completed') = (completed_at IS NOT NULL)),
    CHECK (completed_at >= ordered_at),
    CHECK (status <> 'cancelled' OR NULLIF(btrim(cancellation_reason), '') IS NOT NULL)
);

CREATE TABLE lab_order_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_order_id uuid NOT NULL REFERENCES lab_orders(id),
    lab_test_id uuid NOT NULL REFERENCES lab_tests(id),
    item_number integer NOT NULL CHECK (item_number > 0),
    status varchar(20) NOT NULL DEFAULT 'ordered'
        CHECK (status IN ('ordered', 'collected', 'in_progress', 'completed', 'cancelled')),
    specimen_identifier varchar(100),
    collected_at timestamptz,
    completed_at timestamptz,
    cancellation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lab_order_id, item_number),
    CHECK (status <> 'collected' OR collected_at IS NOT NULL),
    CHECK ((status = 'completed') = (completed_at IS NOT NULL)),
    CHECK (completed_at >= collected_at),
    CHECK (status <> 'cancelled' OR NULLIF(btrim(cancellation_reason), '') IS NOT NULL)
);

-- A panel produces multiple component rows. Corrections create a new revision.
CREATE TABLE lab_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_order_item_id uuid NOT NULL REFERENCES lab_order_items(id),
    component_code varchar(60) NOT NULL CHECK (btrim(component_code) <> ''),
    component_name varchar(200) NOT NULL CHECK (btrim(component_name) <> ''),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    supersedes_result_id uuid,
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'preliminary', 'verified', 'superseded', 'entered_in_error')),
    numeric_value numeric,
    text_value text,
    units varchar(60),
    reference_low numeric,
    reference_high numeric,
    reference_text text,
    abnormal_flag varchar(20) CHECK (abnormal_flag IN
        ('normal', 'low', 'high', 'critical_low', 'critical_high', 'abnormal', 'indeterminate')),
    observed_at timestamptz,
    verified_at timestamptz,
    verified_by_user_id uuid,
    correction_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lab_order_item_id, component_code, revision),
    UNIQUE (id, lab_order_item_id, component_code),
    UNIQUE (supersedes_result_id),
    FOREIGN KEY (supersedes_result_id, lab_order_item_id, component_code)
        REFERENCES lab_results(id, lab_order_item_id, component_code),
    CHECK (supersedes_result_id IS NULL OR supersedes_result_id <> id),
    CHECK (supersedes_result_id IS NULL OR NULLIF(btrim(correction_reason), '') IS NOT NULL),
    CHECK (num_nonnulls(numeric_value, text_value) <= 1),
    CHECK (status NOT IN ('preliminary', 'verified', 'superseded')
        OR (num_nonnulls(numeric_value, text_value) = 1 AND observed_at IS NOT NULL)),
    CHECK (text_value IS NULL OR btrim(text_value) <> ''),
    CHECK (reference_high >= reference_low),
    CHECK ((verified_at IS NULL) = (verified_by_user_id IS NULL)),
    CHECK (status <> 'verified' OR verified_at IS NOT NULL),
    CHECK (verified_at IS NULL OR status IN ('verified', 'superseded', 'entered_in_error')),
    CHECK (verified_at IS NULL OR observed_at IS NOT NULL),
    CHECK (verified_at >= observed_at)
);
CREATE UNIQUE INDEX uq_lab_component_current ON lab_results(lab_order_item_id, component_code)
    WHERE status NOT IN ('superseded', 'entered_in_error');
