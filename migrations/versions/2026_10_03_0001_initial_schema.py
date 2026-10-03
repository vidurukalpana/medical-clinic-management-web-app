"""Initial schema.

Databases created by `create_all` before Alembic are stamped at this revision
after the legacy in-place upgrade (see app/db/initialize.py).

Revision ID: 0001
Revises: 
Create Date: 2026-10-03 10:02:42.682628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate does not detect standalone sequences.
    op.execute(sa.schema.CreateSequence(sa.Sequence("patient_record_number_sequence")))
    op.create_table('patients',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('medical_record_number', sa.String(length=20), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('date_of_birth', sa.Date(), nullable=True),
    sa.Column('gender', sa.Enum('FEMALE', 'MALE', 'OTHER', 'NOT_SPECIFIED', name='patientgender', native_enum=False, length=20), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('emergency_contact', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_patients_full_name'), 'patients', ['full_name'], unique=False)
    op.create_index(op.f('ix_patients_medical_record_number'), 'patients', ['medical_record_number'], unique=True)
    op.create_index(op.f('ix_patients_phone'), 'patients', ['phone'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('PATIENT', 'ADMINISTRATOR', 'DOCTOR', name='userrole', native_enum=False, length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('auth_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auth_sessions_expires_at'), 'auth_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_token_hash'), 'auth_sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('doctors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('registration_number', sa.String(length=50), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doctors_registration_number'), 'doctors', ['registration_number'], unique=True)
    op.create_index(op.f('ix_doctors_user_id'), 'doctors', ['user_id'], unique=True)
    op.create_table('appointments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('booked_by_user_id', sa.Integer(), nullable=True),
    sa.Column('guest_token_hash', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.CheckConstraint("status IN ('scheduled', 'completed', 'cancelled', 'no_show')", name='ck_appointment_status'),
    sa.CheckConstraint('start_at < end_at', name='ck_appointment_time_order'),
    sa.ForeignKeyConstraint(['booked_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointments_booked_by_user_id'), 'appointments', ['booked_by_user_id'], unique=False)
    op.create_index(op.f('ix_appointments_doctor_id'), 'appointments', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_appointments_patient_id'), 'appointments', ['patient_id'], unique=False)
    op.create_index('uq_appointment_doctor_start', 'appointments', ['doctor_id', 'start_at'], unique=True, postgresql_where=sa.text("status <> 'cancelled'"))
    op.create_table('availability',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('slot_duration_minutes', sa.Integer(), server_default='10', nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('slot_duration_minutes BETWEEN 5 AND 240', name='ck_availability_slot_duration'),
    sa.CheckConstraint('start_time < end_time', name='ck_availability_time_order'),
    sa.CheckConstraint('weekday BETWEEN 0 AND 4', name='ck_availability_weekday'),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_availability_doctor_id'), 'availability', ['doctor_id'], unique=False)
    op.create_table('doctor_unavailability',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.CheckConstraint('start_at < end_at', name='ck_doctor_unavailability_time_order'),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doctor_unavailability_doctor_id'), 'doctor_unavailability', ['doctor_id'], unique=False)
    op.create_table('visits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('appointment_id', sa.Integer(), nullable=True),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('visit_date', sa.Date(), nullable=False),
    sa.Column('queue_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.CheckConstraint("status IN ('waiting', 'in_progress', 'completed', 'cancelled')", name='ck_visit_status'),
    sa.CheckConstraint('queue_number > 0', name='ck_visit_queue_number'),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('appointment_id'),
    sa.UniqueConstraint('doctor_id', 'visit_date', 'queue_number', name='uq_visit_queue')
    )
    op.create_index(op.f('ix_visits_doctor_id'), 'visits', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_visits_patient_id'), 'visits', ['patient_id'], unique=False)
    op.create_index('uq_visit_active_patient', 'visits', ['doctor_id', 'visit_date', 'patient_id'], unique=True, postgresql_where=sa.text("status IN ('waiting', 'in_progress')"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_visit_active_patient', table_name='visits', postgresql_where=sa.text("status IN ('waiting', 'in_progress')"))
    op.drop_index(op.f('ix_visits_patient_id'), table_name='visits')
    op.drop_index(op.f('ix_visits_doctor_id'), table_name='visits')
    op.drop_table('visits')
    op.drop_index(op.f('ix_doctor_unavailability_doctor_id'), table_name='doctor_unavailability')
    op.drop_table('doctor_unavailability')
    op.drop_index(op.f('ix_availability_doctor_id'), table_name='availability')
    op.drop_table('availability')
    op.drop_index('uq_appointment_doctor_start', table_name='appointments', postgresql_where=sa.text("status <> 'cancelled'"))
    op.drop_index(op.f('ix_appointments_patient_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_doctor_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_booked_by_user_id'), table_name='appointments')
    op.drop_table('appointments')
    op.drop_index(op.f('ix_doctors_user_id'), table_name='doctors')
    op.drop_index(op.f('ix_doctors_registration_number'), table_name='doctors')
    op.drop_table('doctors')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_token_hash'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_expires_at'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_patients_phone'), table_name='patients')
    op.drop_index(op.f('ix_patients_medical_record_number'), table_name='patients')
    op.drop_index(op.f('ix_patients_full_name'), table_name='patients')
    op.drop_table('patients')
    op.execute(sa.schema.DropSequence(sa.Sequence("patient_record_number_sequence")))
