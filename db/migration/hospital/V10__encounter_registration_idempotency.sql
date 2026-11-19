CREATE TABLE encounter_registration_keys (
    actor_user_id uuid NOT NULL,
    idempotency_key varchar(128) NOT NULL
        CHECK (idempotency_key ~ '^[A-Za-z0-9._~-]{1,128}$'),
    request_digest bytea NOT NULL CHECK (octet_length(request_digest) = 32),
    encounter_id uuid NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (actor_user_id, idempotency_key),
    FOREIGN KEY (encounter_id) REFERENCES medical_encounters(id)
        DEFERRABLE INITIALLY DEFERRED
);
