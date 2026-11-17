-- Single-use interview links: the first browser that opens the interview room is bound to the link.
-- Only a SHA-256 hash of the browser's secret cookie is stored. Idempotent; one statement per line.
ALTER TABLE candidate_invitations ADD COLUMN IF NOT EXISTS room_lock_hash VARCHAR(64);
ALTER TABLE candidate_invitations ADD COLUMN IF NOT EXISTS room_opened_at TIMESTAMPTZ;
