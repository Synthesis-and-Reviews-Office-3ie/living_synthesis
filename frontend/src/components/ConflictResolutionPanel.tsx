'use client';

import { useState, useEffect } from 'react';

interface Conflict {
  id: string;
  living_review_id: string;
  paper_id: string;
  screening_id: string;
  conflict_type: string;
  decision_1: string;
  decision_2: string;
  resolution_status: string;
  final_decision: string | null;
  resolution_notes: string | null;
  resolved_at: string | null;
  created_at: string;
  paper_title: string | null;
  reviewer_1_name: string | null;
  reviewer_2_name: string | null;
  resolved_by_name: string | null;
}

interface ConflictStats {
  total_conflicts: number;
  unresolved_conflicts: number;
  resolved_conflicts: number;
  conflicts_by_type: Record<string, number>;
  average_resolution_time_hours: number | null;
  cohens_kappa: number | null;
  agreement_rate: number | null;
}

interface ConflictResolutionPanelProps {
  reviewId: string;
  accessToken: string;
}

export default function ConflictResolutionPanel({ reviewId, accessToken }: ConflictResolutionPanelProps) {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [stats, setStats] = useState<ConflictStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConflict, setSelectedConflict] = useState<Conflict | null>(null);
  
  // Resolution form
  const [finalDecision, setFinalDecision] = useState<'include' | 'exclude'>('include');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [resolving, setResolving] = useState(false);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('unresolved');

  useEffect(() => {
    fetchConflicts();
  }, [reviewId, statusFilter]);

  const fetchConflicts = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      params.append('include_stats', 'true');

      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/conflicts?${params}`,
        {
          headers: { 'Authorization': `Bearer ${accessToken}` }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch conflicts');
      }

      const data = await response.json();
      setConflicts(data.conflicts);
      if (data.stats) {
        setStats(data.stats);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedConflict) return;

    setResolving(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/conflicts/${selectedConflict.id}/resolve`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            final_decision: finalDecision,
            resolution_notes: resolutionNotes || null
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to resolve conflict');
      }

      // Reset form and close modal
      setSelectedConflict(null);
      setFinalDecision('include');
      setResolutionNotes('');

      // Refresh conflicts
      await fetchConflicts();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setResolving(false);
    }
  };

  const handleDetectConflicts = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/reviews/${reviewId}/conflicts/detect`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${accessToken}` }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to detect conflicts');
      }

      await fetchConflicts();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getDecisionBadge = (decision: string) => {
    const colors: Record<string, string> = {
      include: '#10b981',
      exclude: '#ef4444',
      maybe: '#f59e0b'
    };
    const color = colors[decision] || '#6b7280';
    
    return (
      <span style={{
        padding: '0.25rem 0.625rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: '600',
        backgroundColor: `${color}20`,
        color: color
      }}>
        {decision.toUpperCase()}
      </span>
    );
  };

  const getKappaInterpretation = (kappa: number): { label: string; color: string } => {
    if (kappa >= 0.81) return { label: 'Excellent', color: '#10b981' };
    if (kappa >= 0.61) return { label: 'Good', color: '#3b82f6' };
    if (kappa >= 0.41) return { label: 'Moderate', color: '#f59e0b' };
    if (kappa >= 0.21) return { label: 'Fair', color: '#f97316' };
    return { label: 'Poor', color: '#ef4444' };
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
            🔄 Conflict Resolution
          </h3>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', margin: 0 }}>
            Manage screening conflicts between reviewers
          </p>
        </div>

        <button
          onClick={handleDetectConflicts}
          disabled={loading}
          style={{
            padding: '0.625rem 1.25rem',
            backgroundColor: loading ? '#9ca3af' : '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
            fontWeight: '500',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          🔍 Detect Conflicts
        </button>
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
              Total Conflicts
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#111827' }}>
              {stats.total_conflicts}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Unresolved
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#f59e0b' }}>
              {stats.unresolved_conflicts}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Agreement Rate
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#10b981' }}>
              {stats.agreement_rate !== null ? `${stats.agreement_rate}%` : 'N/A'}
            </div>
          </div>

          {stats.cohens_kappa !== null && (
            <div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
                Cohen's Kappa (κ)
              </div>
              <div style={{ 
                fontSize: '1.75rem', 
                fontWeight: '700', 
                color: getKappaInterpretation(stats.cohens_kappa).color 
              }}>
                {stats.cohens_kappa.toFixed(3)}
              </div>
              <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '0.125rem' }}>
                {getKappaInterpretation(stats.cohens_kappa).label}
              </div>
            </div>
          )}
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
          <option value="unresolved">Unresolved</option>
          <option value="resolved">Resolved</option>
        </select>

        <button
          onClick={() => setStatusFilter('unresolved')}
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

      {/* Conflicts List */}
      {loading && conflicts.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '3rem',
          color: '#9ca3af',
          backgroundColor: 'white',
          borderRadius: '0.75rem',
          border: '1px solid #e5e7eb'
        }}>
          Loading conflicts...
        </div>
      ) : conflicts.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '3rem',
          color: '#9ca3af',
          backgroundColor: 'white',
          borderRadius: '0.75rem',
          border: '1px solid #e5e7eb'
        }}>
          {statusFilter === 'unresolved'
            ? '🎉 No unresolved conflicts! Great inter-rater reliability.'
            : 'No conflicts found.'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {conflicts.map(conflict => (
            <div
              key={conflict.id}
              style={{
                backgroundColor: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '0.75rem',
                padding: '1.25rem'
              }}
            >
              {/* Conflict Header */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '1rem'
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: '0.9375rem',
                    fontWeight: '600',
                    color: '#111827',
                    marginBottom: '0.375rem'
                  }}>
                    {conflict.paper_title || `Paper #${conflict.paper_id.slice(0, 8)}...`}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: '#6b7280' }}>
                    Created {new Date(conflict.created_at).toLocaleDateString()}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span style={{
                    padding: '0.25rem 0.625rem',
                    borderRadius: '9999px',
                    fontSize: '0.75rem',
                    fontWeight: '600',
                    backgroundColor: conflict.resolution_status === 'resolved' ? '#10b98120' : '#f59e0b20',
                    color: conflict.resolution_status === 'resolved' ? '#10b981' : '#f59e0b'
                  }}>
                    {conflict.resolution_status.toUpperCase()}
                  </span>
                  
                  {conflict.resolution_status === 'unresolved' && (
                    <button
                      onClick={() => {
                        setSelectedConflict(conflict);
                        setFinalDecision('include');
                        setResolutionNotes('');
                      }}
                      style={{
                        padding: '0.375rem 0.75rem',
                        backgroundColor: '#3b82f6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.375rem',
                        fontSize: '0.8125rem',
                        cursor: 'pointer',
                        fontWeight: '500'
                      }}
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>

              {/* Side-by-Side Decisions */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '0.75rem',
                marginBottom: conflict.resolution_status === 'resolved' ? '0.75rem' : 0
              }}>
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#f9fafb',
                  borderRadius: '0.5rem',
                  border: '1px solid #e5e7eb'
                }}>
                  <div style={{
                    fontSize: '0.6875rem',
                    color: '#6b7280',
                    marginBottom: '0.375rem',
                    fontWeight: '600',
                    textTransform: 'uppercase'
                  }}>
                    Reviewer 1
                  </div>
                  {getDecisionBadge(conflict.decision_1)}
                  {conflict.reviewer_1_name && (
                    <div style={{ fontSize: '0.8125rem', color: '#6b7280', marginTop: '0.375rem' }}>
                      {conflict.reviewer_1_name}
                    </div>
                  )}
                </div>

                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#f9fafb',
                  borderRadius: '0.5rem',
                  border: '1px solid #e5e7eb'
                }}>
                  <div style={{
                    fontSize: '0.6875rem',
                    color: '#6b7280',
                    marginBottom: '0.375rem',
                    fontWeight: '600',
                    textTransform: 'uppercase'
                  }}>
                    Reviewer 2
                  </div>
                  {getDecisionBadge(conflict.decision_2)}
                  {conflict.reviewer_2_name && (
                    <div style={{ fontSize: '0.8125rem', color: '#6b7280', marginTop: '0.375rem' }}>
                      {conflict.reviewer_2_name}
                    </div>
                  )}
                </div>
              </div>

              {/* Resolution Info */}
              {conflict.resolution_status === 'resolved' && conflict.final_decision && (
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#10b98110',
                  border: '1px solid #10b981',
                  borderRadius: '0.5rem'
                }}>
                  <div style={{
                    fontSize: '0.6875rem',
                    color: '#059669',
                    marginBottom: '0.375rem',
                    fontWeight: '600'
                  }}>
                    ✓ RESOLVED
                  </div>
                  <div style={{ marginBottom: '0.375rem' }}>
                    {getDecisionBadge(conflict.final_decision)}
                  </div>
                  {conflict.resolved_by_name && (
                    <div style={{ fontSize: '0.8125rem', color: '#059669' }}>
                      by {conflict.resolved_by_name}
                      {conflict.resolved_at &&
                        ` on ${new Date(conflict.resolved_at).toLocaleDateString()}`}
                    </div>
                  )}
                  {conflict.resolution_notes && (
                    <div style={{
                      fontSize: '0.8125rem',
                      color: '#374151',
                      marginTop: '0.375rem',
                      fontStyle: 'italic'
                    }}>
                      "{conflict.resolution_notes}"
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Resolution Modal */}
      {selectedConflict && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '0.75rem',
            maxWidth: '500px',
            width: '100%',
            maxHeight: '90vh',
            overflow: 'auto',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '1.25rem',
              borderBottom: '1px solid #e5e7eb'
            }}>
              <h3 style={{
                fontSize: '1.125rem',
                fontWeight: '600',
                color: '#111827',
                margin: 0
              }}>
                Resolve Conflict
              </h3>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '1.25rem' }}>
              <div style={{
                marginBottom: '1.25rem',
                padding: '0.75rem',
                backgroundColor: '#f9fafb',
                borderRadius: '0.5rem'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '0.375rem', fontSize: '0.9375rem' }}>
                  {selectedConflict.paper_title || 'Paper'}
                </div>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '0.75rem',
                marginBottom: '1.25rem'
              }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.375rem' }}>
                    Reviewer 1
                  </div>
                  {getDecisionBadge(selectedConflict.decision_1)}
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.375rem' }}>
                    Reviewer 2
                  </div>
                  {getDecisionBadge(selectedConflict.decision_2)}
                </div>
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{
                  display: 'block',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                  color: '#374151',
                  marginBottom: '0.375rem'
                }}>
                  Final Decision *
                </label>
                <select
                  value={finalDecision}
                  onChange={(e) => setFinalDecision(e.target.value as 'include' | 'exclude')}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem'
                  }}
                >
                  <option value="include">Include</option>
                  <option value="exclude">Exclude</option>
                </select>
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{
                  display: 'block',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                  color: '#374151',
                  marginBottom: '0.375rem'
                }}>
                  Resolution Notes (Optional)
                </label>
                <textarea
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Explain your reasoning..."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem',
                    fontFamily: 'inherit',
                    resize: 'vertical'
                  }}
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '1.25rem',
              borderTop: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.625rem'
            }}>
              <button
                onClick={() => setSelectedConflict(null)}
                disabled={resolving}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: 'white',
                  color: '#374151',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.5rem',
                  fontSize: '0.875rem',
                  cursor: resolving ? 'not-allowed' : 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                disabled={resolving}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: resolving ? '#9ca3af' : '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontSize: '0.875rem',
                  cursor: resolving ? 'not-allowed' : 'pointer',
                  fontWeight: '500'
                }}
              >
                {resolving ? 'Resolving...' : 'Confirm Resolution'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
