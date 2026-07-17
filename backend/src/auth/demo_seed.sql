-- Synthetic development-only accounts. See backend/README.md for credentials.
INSERT INTO users (username, password_hash, role, is_active)
VALUES
    ('manager', '$argon2id$v=19$m=65536,t=3,p=4$fl2NLT/h7T0qRP8tv5D7cg$5LM5rKU2wok6az0ZWBSlcKC5wTjYdTeoTAYh3tA7yRA', 'manager', 1),
    ('customer', '$argon2id$v=19$m=65536,t=3,p=4$ywreARmk8rI7oFnZQ7kdRw$SIOs/oqgmERI4xtBSe6o61Ev++fxEBiGSN9fbGkzOHI', 'customer', 1),
    ('rep', '$argon2id$v=19$m=65536,t=3,p=4$vFMCykskir0765MUlBwu6w$D+twwBj9G/FHPervH2eoRyUZrR10sHIlQUysEBD4s2Q', 'rep', 1),
    ('rep.alex', '$argon2id$v=19$m=65536,t=3,p=4$vFMCykskir0765MUlBwu6w$D+twwBj9G/FHPervH2eoRyUZrR10sHIlQUysEBD4s2Q', 'rep', 1),
    ('rep.jordan', '$argon2id$v=19$m=65536,t=3,p=4$vFMCykskir0765MUlBwu6w$D+twwBj9G/FHPervH2eoRyUZrR10sHIlQUysEBD4s2Q', 'rep', 1),
    ('rep.morgan', '$argon2id$v=19$m=65536,t=3,p=4$vFMCykskir0765MUlBwu6w$D+twwBj9G/FHPervH2eoRyUZrR10sHIlQUysEBD4s2Q', 'rep', 1),
    ('rep.taylor', '$argon2id$v=19$m=65536,t=3,p=4$vFMCykskir0765MUlBwu6w$D+twwBj9G/FHPervH2eoRyUZrR10sHIlQUysEBD4s2Q', 'rep', 1)
ON CONFLICT(username) DO UPDATE SET
    password_hash = excluded.password_hash,
    role = excluded.role,
    is_active = excluded.is_active,
    updated_at = unixepoch();
