"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Loader2, 
  BookOpen, 
  Users, 
  FileCheck, 
  Download,
  ExternalLink,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  HelpCircle,
  RefreshCw,
  AlertCircle,
  Link2,
  Plus,
  FileText,
  X,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import ConflictResolutionPanel from "@/components/ConflictResolutionPanel";
import AssignmentManagementPanel from "@/components/AssignmentManagementPanel";

interface Topic {
  id: string;
  name: string;
  description?: string;
}

interface LivingReview {
  id: string;
  title: string;
  slug: string;
  description?: string;
  status: "draft" | "active" | "paused" | "completed" | "archived";
  current_version: number;
  owner_id?: string;
  population?: string;
  intervention?: string;
  comparator?: string;
  outcomes?: string;
  pico_population?: string;
  pico_intervention?: string;
  pico_comparator?: string;
  pico_outcome?: string;
  prospero_id?: string;
  osf_id?: string;
  topic_id?: string;
  total_screened: number;
  total_included: number;
  total_excluded: number;
  created_at: string;
  updated_at: string;
}

interface ScreeningItem {
  id: string;
  paper_id: string;
  paper_title: string;
  paper_authors: string;
  paper_abstract?: string;
  paper_source: string;
  paper_doi?: string;
  paper_external_id?: string;
  paper_publication_date?: string;
  paper_pdf_url?: string;
  paper_oa_url?: string;
  paper_is_oa?: boolean;
  paper_pdf_available?: boolean;
  ai_decision?: string;
  ai_confidence?: number;
  ai_rationale?: string;
  reviewer1_decision?: string;
  reviewer2_decision?: string;
  final_decision?: string;
  exclusion_reason?: string;
}

interface ScreeningQueueResponse {
  total: number;
  pending: number;
  conflicts: number;
  items: ScreeningItem[];
}

export default function ReviewDetailPage() {
  const params = useParams();
  const reviewId = params.id as string;
  const { user, loading, accessToken } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedTopicId, setSelectedTopicId] = useState<string>("");
  const [showTopicSelector, setShowTopicSelector] = useState(false);
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [currentPaperIndex, setCurrentPaperIndex] = useState(0);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  // Function to open PDF viewer
  const openPdfViewer = async (paperId: string, source: string, externalId?: string) => {
    setPdfLoading(true);
    setPdfViewerOpen(true);
    
    try {
      // For arXiv, we can construct the URL directly
      if (source === 'arxiv' && externalId) {
        const cleanId = externalId.replace(/^arxiv:/i, '').replace(/\.pdf$/, '');
        setPdfUrl(`https://arxiv.org/pdf/${cleanId}.pdf`);
        setPdfLoading(false);
        return;
      }
      
      // For other sources, fetch from our API
      const response = await api.get(`/papers/${paperId}/pdf/url`);
      if (response.data?.pdf_url) {
        setPdfUrl(response.data.pdf_url);
      } else {
        console.error('No PDF URL returned');
        setPdfUrl(null);
        setPdfViewerOpen(false);
      }
    } catch (error) {
      console.error('Failed to get PDF URL:', error);
      setPdfUrl(null);
      setPdfViewerOpen(false);
      // Optionally show a toast/alert here
    } finally {
      setPdfLoading(false);
    }
  };

  const closePdfViewer = () => {
    setPdfViewerOpen(false);
    setPdfUrl(null);
  };

  const { data: review, isLoading } = useQuery({
    queryKey: ["living-review", reviewId],
    queryFn: async () => {
      const response = await api.get(`/reviews/${reviewId}`);
      return response.data as LivingReview;
    },
    enabled: !!user && !!reviewId,
  });

  const { data: screeningData, refetch: refetchScreening } = useQuery({
    queryKey: ["screening-queue", reviewId],
    queryFn: async () => {
      const response = await api.get(`/reviews/${reviewId}/screening`);
      return response.data as ScreeningQueueResponse;
    },
    enabled: !!user && !!reviewId,
  });

  // Fetch available topics for linking
  const { data: topics } = useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      const response = await api.get("/topics");
      return response.data as Topic[];
    },
    enabled: !!user,
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/reviews/${reviewId}/sync-papers`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["screening-queue", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["living-review", reviewId] });
    },
  });

  // Mutation to link a topic to this review
  const linkTopicMutation = useMutation({
    mutationFn: async (topicId: string) => {
      const response = await api.put(`/reviews/${reviewId}`, { topic_id: topicId });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["living-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["screening-queue", reviewId] });
      setShowTopicSelector(false);
      setSelectedTopicId("");
      // Auto-sync papers after linking
      syncMutation.mutate();
    },
  });

  const screenMutation = useMutation({
    mutationFn: async ({ paperId, decision, notes }: { paperId: string; decision: string; notes?: string }) => {
      const response = await api.post(`/reviews/${reviewId}/screening`, {
        decisions: [{
          paper_id: paperId,
          decision,
          reason: notes,
        }],
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["screening-queue", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["living-review", reviewId] });
      // Auto-advance to next unscreened paper
      if (screeningData?.items) {
        const nextPendingIndex = screeningData.items.findIndex((p, i) => i > currentPaperIndex && !p.final_decision);
        if (nextPendingIndex !== -1) {
          setCurrentPaperIndex(nextPendingIndex);
        } else {
          // Try to find any pending paper
          const anyPendingIndex = screeningData.items.findIndex(p => !p.final_decision);
          if (anyPendingIndex !== -1 && anyPendingIndex !== currentPaperIndex) {
            setCurrentPaperIndex(anyPendingIndex);
          }
        }
      }
    },
  });

  const statusMutation = useMutation({
    mutationFn: async (newStatus: string) => {
      const response = await api.put(`/reviews/${reviewId}`, { status: newStatus });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["living-review", reviewId] });
    },
  });

  if (loading || isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </DashboardLayout>
    );
  }

  if (!user || !review) {
    return null;
  }

  const statusColors = {
    draft: "secondary",
    active: "default",
    paused: "outline",
    completed: "default",
    archived: "secondary",
  } as const;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/reviews">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">{review.title}</h1>
                <Badge variant={statusColors[review.status]}>{review.status}</Badge>
              </div>
              <p className="text-muted-foreground">
                Version {review.current_version} • Updated {new Date(review.updated_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {review.status === "draft" && (
              <Button onClick={() => statusMutation.mutate("active")}>
                <Play className="mr-2 h-4 w-4" />
                Activate
              </Button>
            )}
            {review.status === "active" && (
              <Button variant="outline" onClick={() => statusMutation.mutate("paused")}>
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            {review.status === "paused" && (
              <Button onClick={() => statusMutation.mutate("active")}>
                <Play className="mr-2 h-4 w-4" />
                Resume
              </Button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Papers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{screeningData?.total || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Pending</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{screeningData?.pending || 0}</div>
              <p className="text-xs text-muted-foreground">
                {screeningData?.total && screeningData.total > 0 
                  ? `${Math.round(((screeningData.total - screeningData.pending) / screeningData.total) * 100)}% done`
                  : "0%"
                }
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Included</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{review.total_included}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Conflicts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{screeningData?.conflicts || 0}</div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="screening" className="space-y-4">
          <TabsList>
            <TabsTrigger value="screening">Screening ({screeningData?.pending || 0})</TabsTrigger>
            <TabsTrigger value="assignments">
              <Users className="mr-1.5 h-4 w-4" />
              Team & Assignments
            </TabsTrigger>
            <TabsTrigger value="conflicts">
              <AlertTriangle className="mr-1.5 h-4 w-4" />
              Conflicts ({screeningData?.conflicts || 0})
            </TabsTrigger>
            <TabsTrigger value="criteria">PICO Criteria</TabsTrigger>
            <TabsTrigger value="export">Export</TabsTrigger>
          </TabsList>

          <TabsContent value="screening" className="space-y-4">
            {!screeningData?.items?.length || !screeningData.items.find(p => !p.final_decision) ? (
              <Card className="border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-12">
                  {!review.topic_id ? (
                    <>
                      <Link2 className="h-12 w-12 text-yellow-500 mb-4" />
                      <h3 className="font-semibold text-lg mb-2">No Topic Linked</h3>
                      <p className="text-muted-foreground text-center max-w-md mb-6">
                        Link a topic to get papers for screening, or create a new topic first.
                      </p>
                      
                      {showTopicSelector ? (
                        <div className="flex flex-col items-center gap-4 w-full max-w-sm">
                          <Select value={selectedTopicId} onValueChange={setSelectedTopicId}>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select a topic..." />
                            </SelectTrigger>
                            <SelectContent>
                              {topics?.map((topic) => (
                                <SelectItem key={topic.id} value={topic.id}>
                                  {topic.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              onClick={() => {
                                setShowTopicSelector(false);
                                setSelectedTopicId("");
                              }}
                            >
                              Cancel
                            </Button>
                            <Button
                              onClick={() => selectedTopicId && linkTopicMutation.mutate(selectedTopicId)}
                              disabled={!selectedTopicId || linkTopicMutation.isPending}
                            >
                              {linkTopicMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                              <Link2 className="mr-2 h-4 w-4" />
                              Link Topic
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-3">
                          {topics && topics.length > 0 ? (
                            <Button onClick={() => setShowTopicSelector(true)}>
                              <Link2 className="mr-2 h-4 w-4" />
                              Link Existing Topic
                            </Button>
                          ) : null}
                          <Button variant="outline" asChild>
                            <Link href="/topics/new">
                              <Plus className="mr-2 h-4 w-4" />
                              Create New Topic
                            </Link>
                          </Button>
                        </div>
                      )}
                    </>
                  ) : screeningData?.total === 0 ? (
                    <>
                      <RefreshCw className="h-12 w-12 text-muted-foreground mb-4" />
                      <h3 className="font-semibold text-lg mb-2">No Papers Yet</h3>
                      <p className="text-muted-foreground text-center mb-4">
                        Sync papers from your topic to start screening.
                      </p>
                      <Button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
                        {syncMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Sync Papers
                      </Button>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="h-12 w-12 text-green-500 mb-4" />
                      <h3 className="font-semibold text-lg mb-2">All caught up!</h3>
                      <p className="text-muted-foreground text-center">
                        All papers have been screened. New papers will appear when your topic finds new research.
                      </p>
                      <Button variant="outline" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending} className="mt-4">
                        {syncMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Check for New Papers
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            ) : (
              (() => {
                const currentPaper = screeningData.items[currentPaperIndex];
                const totalPapers = screeningData.items.length;
                
                if (!currentPaper) return null;
                
                return (
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0 pr-4">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm text-muted-foreground">
                              {currentPaperIndex + 1} of {totalPapers}
                            </span>
                            {currentPaper.final_decision && (
                              <Badge variant={
                                currentPaper.final_decision === 'include' ? 'default' :
                                currentPaper.final_decision === 'exclude' ? 'destructive' : 'secondary'
                              }>
                                {currentPaper.final_decision}
                              </Badge>
                            )}
                          </div>
                          <CardTitle className="text-lg">{currentPaper.paper_title}</CardTitle>
                          <CardDescription>{currentPaper.paper_authors}</CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          {currentPaper.paper_pdf_available && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openPdfViewer(
                                currentPaper.paper_id,
                                currentPaper.paper_source,
                                currentPaper.paper_external_id
                              )}
                              disabled={pdfLoading}
                            >
                              {pdfLoading ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <FileText className="mr-2 h-4 w-4" />
                              )}
                              View PDF
                            </Button>
                          )}
                          <Badge variant="outline">{currentPaper.paper_source}</Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {currentPaper.paper_abstract && (
                        <div>
                          <h4 className="font-medium mb-2">Abstract</h4>
                          <p className="text-sm text-muted-foreground leading-relaxed">
                            {currentPaper.paper_abstract}
                          </p>
                        </div>
                      )}
                      
                      <div className="flex items-center justify-between pt-4 border-t">
                        {/* Navigation controls */}
                        <div className="flex items-center gap-1">
                          {/* First page */}
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => setCurrentPaperIndex(0)}
                            disabled={currentPaperIndex === 0}
                            title="First paper"
                          >
                            <ChevronLeft className="h-4 w-4" />
                            <ChevronLeft className="h-4 w-4 -ml-3" />
                          </Button>
                          {/* Previous */}
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => setCurrentPaperIndex(Math.max(0, currentPaperIndex - 1))}
                            disabled={currentPaperIndex === 0}
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          
                          {/* Page input */}
                          <div className="flex items-center gap-1 mx-2">
                            <input
                              type="number"
                              min={1}
                              max={totalPapers}
                              value={currentPaperIndex + 1}
                              onChange={(e) => {
                                const val = parseInt(e.target.value);
                                if (!isNaN(val) && val >= 1 && val <= totalPapers) {
                                  setCurrentPaperIndex(val - 1);
                                }
                              }}
                              className="w-16 h-9 text-center border rounded-md text-sm"
                            />
                            <span className="text-sm text-muted-foreground">
                              of {totalPapers}
                            </span>
                          </div>
                          
                          {/* Next */}
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => setCurrentPaperIndex(Math.min(totalPapers - 1, currentPaperIndex + 1))}
                            disabled={currentPaperIndex === totalPapers - 1}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                          {/* Last page */}
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => setCurrentPaperIndex(totalPapers - 1)}
                            disabled={currentPaperIndex === totalPapers - 1}
                            title="Last paper"
                          >
                            <ChevronRight className="h-4 w-4" />
                            <ChevronRight className="h-4 w-4 -ml-3" />
                          </Button>
                          
                          {/* Jump to next pending */}
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="ml-2 text-xs"
                            onClick={() => {
                              const nextPending = screeningData.items.findIndex((p, i) => i > currentPaperIndex && !p.final_decision);
                              if (nextPending !== -1) {
                                setCurrentPaperIndex(nextPending);
                              } else {
                                // Wrap around
                                const firstPending = screeningData.items.findIndex(p => !p.final_decision);
                                if (firstPending !== -1) setCurrentPaperIndex(firstPending);
                              }
                            }}
                            disabled={!screeningData.items.some(p => !p.final_decision)}
                          >
                            Next pending →
                          </Button>
                        </div>
                        
                        {/* Decision buttons */}
                        <div className="flex items-center gap-2">
                          <Button 
                            variant="outline" 
                            size="lg"
                            onClick={() => {
                              screenMutation.mutate({ 
                                paperId: currentPaper.paper_id, 
                                decision: "exclude" 
                              });
                            }}
                            disabled={screenMutation.isPending || !!currentPaper.final_decision}
                          >
                            <XCircle className="mr-2 h-4 w-4 text-red-500" />
                            Exclude
                          </Button>
                          <Button 
                            variant="outline" 
                            size="lg"
                            onClick={() => {
                              screenMutation.mutate({ 
                                paperId: currentPaper.paper_id, 
                                decision: "maybe" 
                              });
                            }}
                            disabled={screenMutation.isPending || !!currentPaper.final_decision}
                          >
                            <HelpCircle className="mr-2 h-4 w-4 text-yellow-500" />
                            Maybe
                          </Button>
                          <Button 
                            size="lg"
                            onClick={() => {
                              screenMutation.mutate({ 
                                paperId: currentPaper.paper_id, 
                                decision: "include" 
                              });
                            }}
                            disabled={screenMutation.isPending || !!currentPaper.final_decision}
                          >
                            <CheckCircle className="mr-2 h-4 w-4" />
                            Include
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })()
            )}
          </TabsContent>

          {/* Team & Assignments Tab */}
          <TabsContent value="assignments" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {accessToken ? (
                  <AssignmentManagementPanel
                    reviewId={reviewId}
                    accessToken={accessToken}
                    isOwner={review.owner_id === user?.id}
                  />
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Conflicts Tab */}
          <TabsContent value="conflicts" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                {accessToken ? (
                  <ConflictResolutionPanel
                    reviewId={reviewId}
                    accessToken={accessToken}
                  />
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="criteria" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>PICO Inclusion Criteria</CardTitle>
                <CardDescription>
                  These criteria define what papers should be included in your review
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h4 className="font-medium text-sm mb-1">Population</h4>
                  <p className="text-muted-foreground">
                    {review.population || "Not specified"}
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-sm mb-1">Intervention</h4>
                  <p className="text-muted-foreground">
                    {review.intervention || "Not specified"}
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-sm mb-1">Comparator</h4>
                  <p className="text-muted-foreground">
                    {review.comparator || "Not specified"}
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-sm mb-1">Outcomes</h4>
                  <p className="text-muted-foreground">
                    {review.outcomes || "Not specified"}
                  </p>
                </div>
              </CardContent>
            </Card>

            {(review.prospero_id || review.osf_id) && (
              <Card>
                <CardHeader>
                  <CardTitle>Protocol Registration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {review.prospero_id && (
                    <div className="flex items-center gap-2">
                      <span className="font-medium">PROSPERO:</span>
                      <a 
                        href={`https://www.crd.york.ac.uk/prospero/display_record.php?ID=${review.prospero_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline flex items-center gap-1"
                      >
                        {review.prospero_id}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  )}
                  {review.osf_id && (
                    <div className="flex items-center gap-2">
                      <span className="font-medium">OSF:</span>
                      <a 
                        href={`https://osf.io/${review.osf_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline flex items-center gap-1"
                      >
                        {review.osf_id}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="export" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Export Included Papers</CardTitle>
                <CardDescription>
                  Download your screened papers in various formats for use in reference managers
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Button variant="outline" asChild>
                    <a href={`/api/reviews/${reviewId}/export/ris`} download>
                      <Download className="mr-2 h-4 w-4" />
                      RIS Format
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <a href={`/api/reviews/${reviewId}/export/bibtex`} download>
                      <Download className="mr-2 h-4 w-4" />
                      BibTeX
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <a href={`/api/reviews/${reviewId}/export/csv`} download>
                      <Download className="mr-2 h-4 w-4" />
                      CSV
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <a href={`/api/reviews/${reviewId}/export/json`} download>
                      <Download className="mr-2 h-4 w-4" />
                      JSON
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Public Landing Page</CardTitle>
                <CardDescription>
                  Share your living review with the public
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 bg-muted rounded text-sm">
                    {typeof window !== "undefined" ? window.location.origin : ""}/reviews/public/{review.slug}
                  </code>
                  <Button variant="outline" asChild>
                    <a 
                      href={`/reviews/public/${review.slug}`} 
                      target="_blank" 
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* PDF Viewer Modal */}
      {pdfViewerOpen && pdfUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center">
          <div className="relative w-full h-full max-w-6xl max-h-[90vh] m-4 bg-background rounded-lg overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold">PDF Viewer</h3>
              <Button variant="ghost" size="icon" onClick={closePdfViewer}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="flex-1 overflow-hidden">
              <iframe
                src={pdfUrl}
                className="w-full h-full border-0"
                title="PDF Viewer"
              />
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
