-- PostgreSQL 17 provides gen_random_uuid() natively; no extension privilege needed.
CREATE FUNCTION maintain_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.created_at := OLD.created_at;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE FUNCTION reject_record_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Operation % is prohibited on %', TG_OP, TG_TABLE_NAME
        USING ERRCODE = '23514';
END;
$$;
