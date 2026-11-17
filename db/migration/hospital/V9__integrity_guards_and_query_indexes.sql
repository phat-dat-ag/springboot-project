-- Generic preservation rules only; clinical transition decisions remain in the service.
CREATE FUNCTION protect_finalized_record() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (NEW.status = ANY(string_to_array(TG_ARGV[0], ',')))
        OR (to_jsonb(NEW) - ARRAY['status', 'updated_at', 'reason', 'correction_reason'])
            IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['status', 'updated_at', 'reason', 'correction_reason'])
        OR COALESCE(NULLIF(btrim(to_jsonb(NEW)->>'reason'), ''),
                    NULLIF(btrim(to_jsonb(NEW)->>'correction_reason'), '')) IS NULL
    THEN
        RAISE EXCEPTION 'Finalized % content is immutable; use a correction record', TG_TABLE_NAME
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER protect_signed_note BEFORE UPDATE ON clinical_notes
    FOR EACH ROW WHEN (OLD.signed_at IS NOT NULL)
    EXECUTE FUNCTION protect_finalized_record('entered_in_error');
CREATE TRIGGER protect_verified_result BEFORE UPDATE ON lab_results
    FOR EACH ROW WHEN (OLD.verified_at IS NOT NULL)
    EXECUTE FUNCTION protect_finalized_record('superseded,entered_in_error');
CREATE TRIGGER protect_signed_prescription BEFORE UPDATE ON prescriptions
    FOR EACH ROW WHEN (OLD.signed_at IS NOT NULL)
    EXECUTE FUNCTION protect_finalized_record('cancelled,superseded,entered_in_error');
CREATE TRIGGER protect_completed_encounter BEFORE UPDATE ON medical_encounters
    FOR EACH ROW WHEN (OLD.status IN ('completed', 'entered_in_error'))
    EXECUTE FUNCTION protect_finalized_record('entered_in_error');

-- Serialize item changes against signing to prevent edits after signature.
CREATE FUNCTION protect_prescription_item() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    parent_id uuid;
    parent_status text;
    parent_signed_at timestamptz;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.prescription_id <> OLD.prescription_id THEN
        RAISE EXCEPTION 'Prescription item ownership cannot change' USING ERRCODE = '23514';
    END IF;
    parent_id := NEW.prescription_id;
    SELECT status, signed_at INTO parent_status, parent_signed_at
        FROM prescriptions WHERE id = parent_id FOR UPDATE;
    IF parent_status IS DISTINCT FROM 'draft' OR parent_signed_at IS NOT NULL THEN
        RAISE EXCEPTION 'Items require an unsigned draft prescription' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_prescription_item BEFORE INSERT OR UPDATE ON prescription_items
    FOR EACH ROW EXECUTE FUNCTION protect_prescription_item();

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'patients', 'patient_contacts', 'patient_allergies', 'patient_medical_histories',
        'doctors', 'specialties', 'doctor_specialties', 'medical_encounters',
        'vital_signs', 'clinical_notes', 'follow_up_plans', 'diagnosis_codes',
        'encounter_diagnoses', 'lab_test_categories', 'lab_tests', 'lab_orders',
        'lab_order_items', 'lab_results', 'medication_categories', 'medications',
        'prescriptions', 'prescription_items', 'medical_attachments'
    ] LOOP
        EXECUTE format('CREATE TRIGGER z_maintain_updated_at BEFORE UPDATE ON %I
            FOR EACH ROW EXECUTE FUNCTION maintain_updated_at()', table_name);
    END LOOP;

    FOREACH table_name IN ARRAY ARRAY[
        'encounter_status_histories', 'diagnosis_histories', 'prescription_histories',
        'clinical_audit_logs', 'medical_record_access_logs'
    ] LOOP
        EXECUTE format('CREATE TRIGGER reject_update BEFORE UPDATE ON %I
            FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()', table_name);
    END LOOP;

    -- No cascading deletes. Explicit lifecycle changes preserve clinical provenance.
    FOREACH table_name IN ARRAY ARRAY[
        'patients', 'patient_contacts', 'patient_allergies', 'patient_medical_histories',
        'doctors', 'specialties', 'doctor_specialties', 'medical_encounters',
        'vital_signs', 'clinical_notes', 'encounter_status_histories', 'follow_up_plans',
        'diagnosis_codes', 'encounter_diagnoses', 'diagnosis_histories',
        'lab_test_categories', 'lab_tests', 'lab_orders', 'lab_order_items', 'lab_results',
        'medication_categories', 'medications', 'prescriptions', 'prescription_items',
        'prescription_histories', 'medical_attachments', 'clinical_audit_logs',
        'medical_record_access_logs'
    ] LOOP
        EXECUTE format('CREATE TRIGGER reject_delete BEFORE DELETE ON %I
            FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON %I
            FOR EACH STATEMENT EXECUTE FUNCTION reject_record_mutation()', table_name);
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT finite_timestamps CHECK (%s)',
            table_name,
            CASE WHEN table_name IN ('encounter_status_histories', 'diagnosis_histories',
                'prescription_histories', 'clinical_audit_logs', 'medical_record_access_logs')
            THEN 'isfinite(occurred_at)'
            ELSE 'isfinite(created_at) AND isfinite(updated_at) AND updated_at >= created_at'
            END);
    END LOOP;
END;
$$;

ALTER TABLE medical_encounters ADD CONSTRAINT finite_encounter_times
    CHECK (isfinite(scheduled_at) AND isfinite(started_at) AND isfinite(ended_at));
ALTER TABLE vital_signs ADD CONSTRAINT finite_measurement_time CHECK (isfinite(measured_at));
ALTER TABLE clinical_notes ADD CONSTRAINT finite_signature_time CHECK (isfinite(signed_at));
ALTER TABLE follow_up_plans ADD CONSTRAINT finite_follow_up_time CHECK (isfinite(completed_at));
ALTER TABLE encounter_diagnoses ADD CONSTRAINT finite_diagnosis_time CHECK (isfinite(diagnosed_at));
ALTER TABLE lab_orders ADD CONSTRAINT finite_order_times
    CHECK (isfinite(ordered_at) AND isfinite(completed_at));
ALTER TABLE lab_order_items ADD CONSTRAINT finite_item_times
    CHECK (isfinite(collected_at) AND isfinite(completed_at));
ALTER TABLE lab_results ADD CONSTRAINT finite_result_times
    CHECK (isfinite(observed_at) AND isfinite(verified_at));
ALTER TABLE prescriptions ADD CONSTRAINT finite_prescription_time CHECK (isfinite(signed_at));

DO $$
DECLARE
    table_name text;
    numeric_column record;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['patients', 'patient_contacts', 'doctors', 'specialties',
        'lab_test_categories', 'lab_tests', 'medication_categories', 'medications', 'medical_attachments']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT valid_soft_delete_time
            CHECK (isfinite(deleted_at) AND deleted_at >= created_at)', table_name);
    END LOOP;
    FOR numeric_column IN
        SELECT c.table_name, c.column_name FROM information_schema.columns c
        WHERE c.table_schema = current_schema() AND c.data_type = 'numeric'
            AND c.table_name IN ('vital_signs', 'lab_results', 'prescription_items')
        ORDER BY c.table_name, c.column_name
    LOOP
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I
            CHECK (%I::text NOT IN (''NaN'', ''Infinity'', ''-Infinity''))',
            numeric_column.table_name, 'finite_' || numeric_column.column_name,
            numeric_column.column_name);
    END LOOP;
END;
$$;

CREATE INDEX ix_patient_contacts_patient ON patient_contacts(patient_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_patient_allergies_patient ON patient_allergies(patient_id, status);
CREATE INDEX ix_patient_histories_patient ON patient_medical_histories(patient_id, history_type);
CREATE INDEX ix_doctor_specialties_specialty ON doctor_specialties(specialty_id);
CREATE INDEX ix_encounters_patient_date ON medical_encounters(patient_id, created_at DESC);
CREATE INDEX ix_encounters_doctor_date ON medical_encounters(doctor_id, scheduled_at DESC);
CREATE INDEX ix_vital_signs_encounter_time ON vital_signs(encounter_id, measured_at DESC);
CREATE INDEX ix_notes_encounter_date ON clinical_notes(encounter_id, created_at DESC);
CREATE INDEX ix_notes_author ON clinical_notes(author_doctor_id);
CREATE INDEX ix_encounter_history_time ON encounter_status_histories(encounter_id, occurred_at DESC);
CREATE INDEX ix_follow_up_encounter ON follow_up_plans(encounter_id);
CREATE INDEX ix_follow_up_due ON follow_up_plans(due_on) WHERE status = 'pending';
CREATE INDEX ix_follow_up_doctor ON follow_up_plans(responsible_doctor_id);
CREATE INDEX ix_diagnoses_encounter_status ON encounter_diagnoses(encounter_id, status);
CREATE INDEX ix_diagnoses_code ON encounter_diagnoses(diagnosis_code_id);
CREATE INDEX ix_diagnoses_doctor ON encounter_diagnoses(diagnosing_doctor_id);
CREATE INDEX ix_diagnosis_history_time ON diagnosis_histories(encounter_diagnosis_id, occurred_at DESC);
CREATE INDEX ix_diagnosis_history_previous_code ON diagnosis_histories(previous_code_id);
CREATE INDEX ix_diagnosis_history_new_code ON diagnosis_histories(new_code_id);
CREATE INDEX ix_lab_tests_category ON lab_tests(category_id);
CREATE INDEX ix_lab_orders_encounter_date ON lab_orders(encounter_id, created_at DESC);
CREATE INDEX ix_lab_orders_doctor ON lab_orders(ordering_doctor_id);
CREATE INDEX ix_lab_items_test ON lab_order_items(lab_test_id);
-- Item and result parent lookups are already covered by their composite unique constraints.
CREATE INDEX ix_medications_category ON medications(category_id);
CREATE INDEX ix_prescriptions_encounter_date ON prescriptions(encounter_id, created_at DESC);
CREATE INDEX ix_prescriptions_doctor ON prescriptions(prescribing_doctor_id);
CREATE INDEX ix_prescription_items_medication ON prescription_items(medication_id);
CREATE INDEX ix_prescription_history_time ON prescription_histories(prescription_id, occurred_at DESC);
CREATE INDEX ix_attachments_patient_date ON medical_attachments(patient_id, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX ix_attachments_encounter_patient ON medical_attachments(encounter_id, patient_id);
CREATE INDEX ix_audit_entity_time ON clinical_audit_logs(entity_type, entity_id, occurred_at DESC);
CREATE INDEX ix_audit_patient_time ON clinical_audit_logs(patient_id, occurred_at DESC);
CREATE INDEX ix_access_patient_time ON medical_record_access_logs(patient_id, occurred_at DESC);
