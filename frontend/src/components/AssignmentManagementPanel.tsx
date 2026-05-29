'use client';

import { useState, useEffect } from 'react';

interface TeamMember {
  id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  role: string;
}

interface Assignment {
  id: string;
  living_review_id: string;
  paper_id: string;
  user_id: string;
  assignment_order: number;
  is_blinded: boolean;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  paper_title: string | null;
  user_name: string | null;
}

interface AssignmentStats {
  total_assignments: number;
  pending: number;
  in_progress: number;
  completed: number;
  overdue: number;
  completion_rate: number;
  avg_time_to_complete_hours: number | null;
}

interface AssignmentManagementPanelProps {
  reviewId: string;
  accessToken: string;
  isOwner: boolean;
}

export default function AssignmentManagementPanel({ 
  reviewId, 
  accessToken,
  isOwner 
}: AssignmentManagementPanelProps) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [stats, setStats] = useState<AssignmentStats | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Assignment creation form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedReviewers, setSelectedReviewers] = useState<string[]>([]);
  const [distributionStrategy, setDistributionStrategy] = useState<'balanced' | 'random' | 'round_robin'>('balanced');
  const [reviewersPerPaper, setReviewersPerPaper] = useState(2);
  const [isBlinded, setIsBlinded] = useState(true);
  const [creating, setCreating] = useState(false);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [userFilter, setUserFilter] = useState<string>('');

  // Team management
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'screener' | 'reviewer' | 'viewer'>('screener');
  const [inviting, setInviting] = useState(false);
  const [removingMember, setRemovingMember] = useState<string | null>(null);

  useEffect(() => {
    if (accessToken) {
      fetchAssignments();
      fetchTeamMembers();
    }
  }, [reviewId, statusFilter, userFilter, accessToken]);

  const fetchAssignments = async () => {
    if (!accessToken) return;
    
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (userFilter) params.append('user_id', userFilter);
      params.append('include_stats', 'true');

      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/assignments?${params}`,
        {
          headers: { 'Authorization': `Bearer ${accessToken}` }
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Assignments API error:', response.status, errorText);
        throw new Error(`Failed to fetch assignments (${response.status})`);
      }

      const data = await response.json();
      setAssignments(data.assignments || []);
      if (data.stats) {
        setStats(data.stats);
      }
    } catch (err: any) {
      console.error('Fetch assignments error:', err);
      setError(err.message || 'Network error - please check your connection');
    } finally {
      setLoading(false);
    }
  };

  const fetchTeamMembers = async () => {
    if (!accessToken) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/team`,
        {
          headers: { 'Authorization': `Bearer ${accessToken}` }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setTeamMembers(data || []);
      } else {
        console.error('Team fetch failed:', response.status, await response.text());
      }
    } catch (err) {
      console.error('Failed to fetch team members:', err);
    }
  };

  const handleCreateAssignments = async () => {
    if (selectedReviewers.length === 0) {
      setError('Please select at least one reviewer');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/assignments`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_ids: selectedReviewers,
            distribution_strategy: distributionStrategy,
            reviewers_per_paper: reviewersPerPaper,
            is_blinded: isBlinded
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create assignments');
      }

      // Reset form and refresh
      setShowCreateForm(false);
      setSelectedReviewers([]);
      await fetchAssignments();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleUpdateStatus = async (assignmentId: string, newStatus: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/assignments/${assignmentId}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ status: newStatus })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update assignment');
      }

      await fetchAssignments();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleInviteMember = async () => {
    if (!inviteEmail.trim()) return;
    
    setInviting(true);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/team`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            email: inviteEmail.trim(),
            role: inviteRole
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to invite team member');
      }

      // Reset form and refresh
      setShowInviteForm(false);
      setInviteEmail('');
      setInviteRole('screener');
      await fetchTeamMembers();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setInviting(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!confirm('Are you sure you want to remove this team member?')) return;
    
    setRemovingMember(userId);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/team/${userId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to remove team member');
      }

      await fetchTeamMembers();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRemovingMember(null);
    }
  };

  const handleUpdateMemberRole = async (userId: string, newRole: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/team/${userId}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ role: newRole })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update member role');
      }

      await fetchTeamMembers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      pending: { bg: '#f59e0b20', text: '#f59e0b' },
      in_progress: { bg: '#3b82f620', text: '#3b82f6' },
      completed: { bg: '#10b98120', text: '#10b981' },
      skipped: { bg: '#6b728020', text: '#6b7280' }
    };
    const style = colors[status] || colors.pending;
    
    return (
      <span style={{
        padding: '0.25rem 0.625rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: '600',
        backgroundColor: style.bg,
        color: style.text,
        textTransform: 'uppercase'
      }}>
        {status.replace('_', ' ')}
      </span>
    );
  };

  const toggleReviewer = (userId: string) => {
    setSelectedReviewers(prev => 
      prev.includes(userId) 
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  return (
    <div style={{ marginBottom: '2rem' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem'
      }}>
        <div>
          <h3 style={{
            fontSize: '1.25rem',
            fontWeight: '600',
            marginBottom: '0.5rem',
            color: '#111827'
          }}>
            👥 Paper Assignments
          </h3>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', margin: 0 }}>
            Assign papers to reviewers for screening
          </p>
        </div>

        {isOwner && (
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            style={{
              padding: '0.625rem 1.25rem',
              backgroundColor: showCreateForm ? '#6b7280' : '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            {showCreateForm ? '✕ Cancel' : '+ Assign Papers'}
          </button>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div style={{
          marginBottom: '1rem',
          padding: '1rem',
          backgroundColor: '#fee2e2',
          border: '1px solid #fecaca',
          borderRadius: '0.5rem',
          color: '#991b1b',
          fontSize: '0.875rem'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Team Management Section */}
      <div style={{
        marginBottom: '1.5rem',
        padding: '1.25rem',
        backgroundColor: 'white',
        border: '1px solid #e5e7eb',
        borderRadius: '0.75rem'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem'
        }}>
          <h4 style={{ 
            fontSize: '1rem', 
            fontWeight: '600', 
            color: '#374151',
            margin: 0
          }}>
            📋 Team Members ({teamMembers.length})
          </h4>
          {isOwner && (
            <button
              onClick={() => setShowInviteForm(!showInviteForm)}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: showInviteForm ? '#6b7280' : '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '0.813rem',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              {showInviteForm ? '✕ Cancel' : '+ Add Reviewer'}
            </button>
          )}
        </div>

        {/* Invite Form */}
        {showInviteForm && isOwner && (
          <div style={{
            marginBottom: '1rem',
            padding: '1rem',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '0.5rem'
          }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div style={{ flex: '1', minWidth: '200px' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#374151', marginBottom: '0.25rem' }}>
                  Email Address
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="reviewer@example.com"
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem'
                  }}
                />
              </div>
              <div style={{ minWidth: '140px' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#374151', marginBottom: '0.25rem' }}>
                  Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem',
                    backgroundColor: 'white'
                  }}
                >
                  <option value="admin">Admin</option>
                  <option value="screener">Screener</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
              <button
                onClick={handleInviteMember}
                disabled={inviting || !inviteEmail.trim()}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: inviting || !inviteEmail.trim() ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                  cursor: inviting || !inviteEmail.trim() ? 'not-allowed' : 'pointer'
                }}
              >
                {inviting ? 'Inviting...' : 'Add to Team'}
              </button>
            </div>
            <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.5rem', marginBottom: 0 }}>
              Note: The user must already have an account in the system.
            </p>
          </div>
        )}

        {/* Team Members List */}
        {teamMembers.length === 0 ? (
          <p style={{ color: '#6b7280', fontSize: '0.875rem', textAlign: 'center', padding: '1rem' }}>
            No team members yet. Add reviewers to get started.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {teamMembers.map((member) => (
              <div 
                key={member.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem',
                  backgroundColor: '#f9fafb',
                  borderRadius: '0.5rem',
                  border: '1px solid #e5e7eb'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    backgroundColor: member.role === 'owner' ? '#3b82f6' : '#10b981',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: '0.875rem',
                    fontWeight: '600'
                  }}>
                    {(member.user_name || member.user_email || '?')[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontWeight: '500', fontSize: '0.875rem', color: '#111827' }}>
                      {member.user_name || member.user_email?.split('@')[0] || 'Unknown'}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                      {member.user_email}
                    </div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {isOwner && member.role !== 'owner' ? (
                    <select
                      value={member.role}
                      onChange={(e) => handleUpdateMemberRole(member.user_id, e.target.value)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        border: '1px solid #d1d5db',
                        borderRadius: '0.25rem',
                        fontSize: '0.75rem',
                        backgroundColor: 'white'
                      }}
                    >
                      <option value="admin">Admin</option>
                      <option value="screener">Screener</option>
                      <option value="reviewer">Reviewer</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  ) : (
                    <span style={{
                      padding: '0.25rem 0.625rem',
                      backgroundColor: member.role === 'owner' ? '#dbeafe' : '#e5e7eb',
                      color: member.role === 'owner' ? '#1e40af' : '#374151',
                      borderRadius: '0.25rem',
                      fontSize: '0.75rem',
                      fontWeight: '500',
                      textTransform: 'capitalize'
                    }}>
                      {member.role}
                    </span>
                  )}
                  
                  {isOwner && member.role !== 'owner' && (
                    <button
                      onClick={() => handleRemoveMember(member.user_id)}
                      disabled={removingMember === member.user_id}
                      style={{
                        padding: '0.25rem 0.5rem',
                        backgroundColor: 'transparent',
                        color: '#ef4444',
                        border: '1px solid #ef4444',
                        borderRadius: '0.25rem',
                        fontSize: '0.75rem',
                        cursor: removingMember === member.user_id ? 'not-allowed' : 'pointer',
                        opacity: removingMember === member.user_id ? 0.5 : 1
                      }}
                    >
                      {removingMember === member.user_id ? '...' : '✕'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Assignment Form */}
      {showCreateForm && isOwner && (
        <div style={{
          marginBottom: '1.5rem',
          padding: '1.5rem',
          backgroundColor: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: '0.75rem'
        }}>
          <h4 style={{ 
            fontSize: '1rem', 
            fontWeight: '600', 
            marginBottom: '1rem',
            color: '#0c4a6e'
          }}>
            Create New Assignments
          </h4>

          {/* Select Reviewers */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: '500',
              color: '#374151',
              marginBottom: '0.5rem'
            }}>
              Select Reviewers *
            </label>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.5rem'
            }}>
              {teamMembers.length === 0 ? (
                <p style={{ color: '#6b7280', fontSize: '0.875rem', fontStyle: 'italic' }}>
                  No team members found. Add team members first.
                </p>
              ) : (
                teamMembers.map(member => (
                  <button
                    key={member.user_id}
                    onClick={() => toggleReviewer(member.user_id)}
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: selectedReviewers.includes(member.user_id) ? '#3b82f6' : 'white',
                      color: selectedReviewers.includes(member.user_id) ? 'white' : '#374151',
                      border: '1px solid',
                      borderColor: selectedReviewers.includes(member.user_id) ? '#3b82f6' : '#d1d5db',
                      borderRadius: '0.5rem',
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.375rem'
                    }}
                  >
                    {selectedReviewers.includes(member.user_id) && '✓ '}
                    {member.user_name || member.user_email}
                    <span style={{ 
                      fontSize: '0.75rem', 
                      opacity: 0.7,
                      textTransform: 'capitalize'
                    }}>
                      ({member.role})
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Distribution Settings */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '1rem',
            marginBottom: '1rem'
          }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '500',
                color: '#374151',
                marginBottom: '0.375rem'
              }}>
                Distribution Strategy
              </label>
              <select
                value={distributionStrategy}
                onChange={(e) => setDistributionStrategy(e.target.value as any)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                  backgroundColor: 'white'
                }}
              >
                <option value="balanced">Balanced (Equal distribution)</option>
                <option value="random">Random</option>
                <option value="round_robin">Round Robin</option>
              </select>
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '500',
                color: '#374151',
                marginBottom: '0.375rem'
              }}>
                Reviewers per Paper
              </label>
              <select
                value={reviewersPerPaper}
                onChange={(e) => setReviewersPerPaper(parseInt(e.target.value))}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                  backgroundColor: 'white'
                }}
              >
                <option value={1}>1 (Single screening)</option>
                <option value={2}>2 (Dual screening)</option>
                <option value={3}>3 (Triple screening)</option>
              </select>
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '500',
                color: '#374151',
                marginBottom: '0.375rem'
              }}>
                Blinding
              </label>
              <select
                value={isBlinded ? 'yes' : 'no'}
                onChange={(e) => setIsBlinded(e.target.value === 'yes')}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                  backgroundColor: 'white'
                }}
              >
                <option value="yes">Blinded (reviewers can't see each other's decisions)</option>
                <option value="no">Not blinded</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleCreateAssignments}
            disabled={creating || selectedReviewers.length === 0}
            style={{
              padding: '0.625rem 1.5rem',
              backgroundColor: creating || selectedReviewers.length === 0 ? '#9ca3af' : '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
              fontWeight: '500',
              cursor: creating || selectedReviewers.length === 0 ? 'not-allowed' : 'pointer'
            }}
          >
            {creating ? 'Creating...' : `Assign Papers to ${selectedReviewers.length} Reviewer(s)`}
          </button>
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <div style={{
          marginBottom: '1.5rem',
          padding: '1.25rem',
          backgroundColor: '#f9fafb',
          border: '1px solid #e5e7eb',
          borderRadius: '0.75rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '1.5rem'
        }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Total Assignments
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#111827' }}>
              {stats.total_assignments}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Pending
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#f59e0b' }}>
              {stats.pending}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              In Progress
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#3b82f6' }}>
              {stats.in_progress}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Completed
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#10b981' }}>
              {stats.completed}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{
        marginBottom: '1rem',
        display: 'flex',
        gap: '0.75rem',
        alignItems: 'center'
      }}>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid #d1d5db',
            borderRadius: '0.375rem',
            fontSize: '0.875rem',
            backgroundColor: 'white'
          }}
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="skipped">Skipped</option>
        </select>

        <select
          value={userFilter}
          onChange={(e) => setUserFilter(e.target.value)}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid #d1d5db',
            borderRadius: '0.375rem',
            fontSize: '0.875rem',
            backgroundColor: 'white'
          }}
        >
          <option value="">All Reviewers</option>
          {teamMembers.map(member => (
            <option key={member.user_id} value={member.user_id}>
              {member.user_name || member.user_email}
            </option>
          ))}
        </select>

        <button
          onClick={() => { setStatusFilter(''); setUserFilter(''); }}
          style={{
            padding: '0.5rem 0.75rem',
            backgroundColor: 'transparent',
            color: '#6b7280',
            border: '1px solid #d1d5db',
            borderRadius: '0.375rem',
            fontSize: '0.875rem',
            cursor: 'pointer'
          }}
        >
          Reset
        </button>
      </div>

      {/* Assignments List */}
      {loading && assignments.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '3rem',
          color: '#9ca3af',
          backgroundColor: 'white',
          borderRadius: '0.75rem',
          border: '1px solid #e5e7eb'
        }}>
          Loading assignments...
        </div>
      ) : assignments.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '3rem',
          color: '#9ca3af',
          backgroundColor: 'white',
          borderRadius: '0.75rem',
          border: '1px solid #e5e7eb'
        }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📋</div>
          <h4 style={{ fontWeight: '600', color: '#374151', marginBottom: '0.5rem' }}>
            No Assignments Yet
          </h4>
          <p style={{ fontSize: '0.875rem' }}>
            {isOwner 
              ? 'Click "Assign Papers" to distribute papers among your team members.'
              : 'No papers have been assigned to reviewers yet.'}
          </p>
        </div>
      ) : (
        <div style={{ 
          backgroundColor: 'white',
          border: '1px solid #e5e7eb',
          borderRadius: '0.75rem',
          overflow: 'hidden'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#f9fafb' }}>
                <th style={{ 
                  padding: '0.75rem 1rem', 
                  textAlign: 'left', 
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#6b7280',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid #e5e7eb'
                }}>
                  Paper
                </th>
                <th style={{ 
                  padding: '0.75rem 1rem', 
                  textAlign: 'left', 
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#6b7280',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid #e5e7eb'
                }}>
                  Reviewer
                </th>
                <th style={{ 
                  padding: '0.75rem 1rem', 
                  textAlign: 'center', 
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#6b7280',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid #e5e7eb'
                }}>
                  Order
                </th>
                <th style={{ 
                  padding: '0.75rem 1rem', 
                  textAlign: 'center', 
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#6b7280',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid #e5e7eb'
                }}>
                  Status
                </th>
                {isOwner && (
                  <th style={{ 
                    padding: '0.75rem 1rem', 
                    textAlign: 'right', 
                    fontSize: '0.75rem',
                    fontWeight: '600',
                    color: '#6b7280',
                    textTransform: 'uppercase',
                    borderBottom: '1px solid #e5e7eb'
                  }}>
                    Actions
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment, idx) => (
                <tr 
                  key={assignment.id}
                  style={{ 
                    borderBottom: idx < assignments.length - 1 ? '1px solid #e5e7eb' : 'none'
                  }}
                >
                  <td style={{ 
                    padding: '0.75rem 1rem',
                    fontSize: '0.875rem',
                    color: '#111827',
                    maxWidth: '300px'
                  }}>
                    <div style={{ 
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {assignment.paper_title || `Paper ${assignment.paper_id.slice(0, 8)}...`}
                    </div>
                  </td>
                  <td style={{ 
                    padding: '0.75rem 1rem',
                    fontSize: '0.875rem',
                    color: '#374151'
                  }}>
                    {assignment.user_name || assignment.user_id.slice(0, 8)}
                    {assignment.is_blinded && (
                      <span style={{ 
                        marginLeft: '0.5rem',
                        fontSize: '0.75rem',
                        color: '#9ca3af'
                      }}>
                        🔒
                      </span>
                    )}
                  </td>
                  <td style={{ 
                    padding: '0.75rem 1rem',
                    textAlign: 'center',
                    fontSize: '0.875rem',
                    color: '#6b7280'
                  }}>
                    #{assignment.assignment_order}
                  </td>
                  <td style={{ 
                    padding: '0.75rem 1rem',
                    textAlign: 'center'
                  }}>
                    {getStatusBadge(assignment.status)}
                  </td>
                  {isOwner && (
                    <td style={{ 
                      padding: '0.75rem 1rem',
                      textAlign: 'right'
                    }}>
                      <select
                        value={assignment.status}
                        onChange={(e) => handleUpdateStatus(assignment.id, e.target.value)}
                        style={{
                          padding: '0.25rem 0.5rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '0.25rem',
                          fontSize: '0.75rem',
                          backgroundColor: 'white'
                        }}
                      >
                        <option value="pending">Pending</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                        <option value="skipped">Skipped</option>
                      </select>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
