"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { topicsApi, Topic } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { 
  ArrowLeft, 
  Play, 
  Pause, 
  Pencil, 
  Trash2, 
  Loader2,
  Calendar,
  Search,
  CheckCircle,
  FileText,
  Sparkles,
  ExternalLink,
  TrendingUp,
  BookOpen,
  Unlock,
  BarChart3,
  Zap,
  Check,
  X,
  Library,
  Filter,
  Newspaper,
  ChevronDown,
  ChevronUp,
  History
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useState } from "react";

interface TopicStats {
  total_papers: number;
  reviewed: number;
  included: number;
  pending: number;
  with_summaries: number;
  new_this_week: number;
  top_source: string | null;
  top_source_count: number;
  open_access: number;
  avg_relevance_score: number | null;
  sources: Record<string, number>;
  categories: Record<string, number>;
  monthly_trend: Record<string, number>;
}

interface Paper {
  id: string;
  paper_id: string;
  title: string;
  abstract?: string;
  authors: string[];
  source: string;
  url?: string;
  doi?: string;
  published_date?: string;
  is_oa: boolean;
  summary?: string;
  headline?: string;
  category?: string;
  relevance_score?: number;
  ai_relevance_reason?: string;
  included: boolean;
  reviewed_at?: string;
}

export default function TopicDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const topicId = params.id as string;
  const [isRunning, setIsRunning] = useState(false);
  const [isRunningHistorical, setIsRunningHistorical] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isScoring, setIsScoring] = useState(false);
  const [isGeneratingDigest, setIsGeneratingDigest] = useState(false);
  const [digest, setDigest] = useState<{
    digest: string;
    highlights: Array<{title: string; score: number}>;
    stats: {total: number; high_relevance: number; sources: Record<string, number>};
  } | null>(null);
  const [hideLowRelevance, setHideLowRelevance] = useState(false);
  const [showOnlyCollection, setShowOnlyCollection] = useState(false);
  
  // Smart Filters
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [dateFilter, setDateFilter] = useState<string>('all');
  const [showOnlyOA, setShowOnlyOA] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const { data: topic, isLoading } = useQuery({
    queryKey: ["topic", topicId],
    queryFn: async () => {
      const response = await topicsApi.get(topicId);
      return response.data as Topic;
    },
  });

  const { data: reviewQueue } = useQuery({
    queryKey: ["review-queue", topicId],
    queryFn: async () => {
      const response = await topicsApi.getReviewQueue(topicId);
      return response.data as Paper[];
    },
    enabled: !!topicId,
  });

  const { data: stats } = useQuery({
    queryKey: ["topic-stats", topicId],
    queryFn: async () => {
      const response = await topicsApi.getStats(topicId);
      return response.data as TopicStats;
    },
    enabled: !!topicId,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      topicsApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      toast.success("Topic updated");
    },
    onError: () => {
      toast.error("Failed to update topic");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => topicsApi.delete(id),
    onSuccess: () => {
      toast.success("Topic deleted");
      router.push("/topics");
    },
    onError: () => {
      toast.error("Failed to delete topic");
    },
  });

  const runTopic = async () => {
    setIsRunning(true);
    const startTime = Date.now();
    const initialLastRun = topic?.last_run_at;
    
    try {
      const response = await topicsApi.run(topicId);
      console.log("Run topic response:", response);
      toast.success("Paper search started! This may take a minute.");
      
      // Poll for completion - check every 3 seconds
      // Stop when: 1) last_run_at changes, 2) 2 minutes timeout
      const pollInterval = setInterval(async () => {
        try {
          // Refresh data
          await queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
          const topicResult = await queryClient.fetchQuery({
            queryKey: ["topic", topicId],
            queryFn: async () => {
              const resp = await topicsApi.get(topicId);
              return resp.data;
            },
          });
          await queryClient.invalidateQueries({ queryKey: ["topic-stats", topicId] });
          
          // Check if search completed (last_run_at changed)
          if (topicResult?.last_run_at && topicResult.last_run_at !== initialLastRun) {
            console.log("Search completed - last_run_at changed");
            clearInterval(pollInterval);
            setIsRunning(false);
            toast.success("Paper search complete! Check your results.");
          }
          
          // Also stop after 2 minutes
          if (Date.now() - startTime > 120000) {
            clearInterval(pollInterval);
            setIsRunning(false);
            toast.success("Paper search complete! Check your results.");
          }
        } catch (e) {
          console.error("Poll error:", e);
        }
      }, 3000);
      
    } catch (error: any) {
      console.error("Run topic error:", error);
      setIsRunning(false);
      const detail = error.response?.data?.detail;
      if (error.response?.status === 401) {
        toast.error("Please log in again to run the search");
      } else if (error.response?.status === 404) {
        toast.error("Topic not found");
      } else {
        toast.error(detail || "Failed to run paper search. Please try again.");
      }
    }
    // Note: Don't set isRunning=false here - let the poll detect completion
  };

  // Historical search handler (one-time, no date limit)
  const runHistoricalSearch = async () => {
    setIsRunningHistorical(true);
    const startTime = Date.now();
    const initialLastRun = topic?.last_run_at;
    
    try {
      await topicsApi.runHistorical(topicId);
      toast.success("Historical search started! Fetching all past papers (no date limit). This may take a while...");
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          await queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
          const topicResult = await queryClient.fetchQuery({
            queryKey: ["topic", topicId],
            queryFn: async () => {
              const resp = await topicsApi.get(topicId);
              return resp.data;
            },
          });
          await queryClient.invalidateQueries({ queryKey: ["topic-stats", topicId] });
          
          if (topicResult?.last_run_at && topicResult.last_run_at !== initialLastRun) {
            clearInterval(pollInterval);
            setIsRunningHistorical(false);
            toast.success("Historical search complete! All past papers have been fetched.");
          }
          
          // Stop after 5 minutes for historical (longer than regular)
          if (Date.now() - startTime > 300000) {
            clearInterval(pollInterval);
            setIsRunningHistorical(false);
            toast.success("Historical search complete!");
          }
        } catch (e) {
          console.error("Poll error:", e);
        }
      }, 5000);
      
    } catch (error: any) {
      setIsRunningHistorical(false);
      const detail = error.response?.data?.detail;
      if (error.response?.status === 400) {
        toast.error(detail || "Historical search already done for this topic");
      } else {
        toast.error(detail || "Failed to run historical search");
      }
    }
  };

  // AI Summarize All handler
  const summarizeAll = async () => {
    setIsSummarizing(true);
    try {
      const result = await topicsApi.summarizeAll(topicId);
      toast.success(`Generated ${result.data.summarized} AI summaries`);
      queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic-stats", topicId] });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to generate summaries");
    } finally {
      setIsSummarizing(false);
    }
  };

  // LLM Relevance Scoring handler
  const scoreRelevance = async () => {
    setIsScoring(true);
    try {
      const result = await topicsApi.scoreRelevance(topicId);
      toast.success(result.data.message);
      queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic-stats", topicId] });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to score relevance");
    } finally {
      setIsScoring(false);
    }
  };

  // Generate Weekly AI Digest
  const generateDigest = async () => {
    setIsGeneratingDigest(true);
    try {
      const result = await topicsApi.generateDigest(topicId);
      setDigest(result.data);
      toast.success("Digest generated successfully!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to generate digest");
    } finally {
      setIsGeneratingDigest(false);
    }
  };

  // Quick include/exclude paper handler
  const handlePaperReview = async (paperId: string, included: boolean) => {
    try {
      await topicsApi.reviewPaper(topicId, paperId, included);
      toast.success(included ? "Added to collection" : "Moved to trash (auto-deletes in 30 days)");
      queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topic-stats", topicId] });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to update paper");
    }
  };

  // Computed values from stats
  const summaryPercent = stats ? Math.round((stats.with_summaries / Math.max(stats.total_papers, 1)) * 100) : 0;
  const topSources = stats?.sources ? Object.entries(stats.sources).sort((a, b) => b[1] - a[1]).slice(0, 5) : [];
  const topCategories = stats?.categories ? Object.entries(stats.categories).sort((a, b) => b[1] - a[1]).slice(0, 5) : [];
  
  // Check if any papers have been scored for relevance
  const scoredPapersCount = reviewQueue?.filter((p: Paper) => p.relevance_score !== undefined && p.relevance_score !== null).length || 0;
  const hasScoredPapers = scoredPapersCount > 0;
  
  // Collection stats (excluded papers are moved to trash, so we just count included and pending)
  const includedCount = reviewQueue?.filter((p: Paper) => p.included === true).length || 0;
  const pendingCount = reviewQueue?.filter((p: Paper) => !p.reviewed_at).length || 0;
  const totalVisible = reviewQueue?.length || 0;
  
  // Filter helper function
  const filterPaper = (paper: Paper): boolean => {
    if (showOnlyCollection) return paper.included === true;
    if (sourceFilter !== 'all' && paper.source !== sourceFilter) return false;
    if (dateFilter !== 'all') {
      // If date filter is active but paper has no date, exclude it
      if (!paper.published_date) return false;
      const paperDate = new Date(paper.published_date);
      const now = new Date();
      const diffDays = Math.floor((now.getTime() - paperDate.getTime()) / (1000 * 60 * 60 * 24));
      if (dateFilter === 'week' && diffDays > 7) return false;
      if (dateFilter === 'month' && diffDays > 30) return false;
      if (dateFilter === '3months' && diffDays > 90) return false;
      if (dateFilter === 'year' && diffDays > 365) return false;
    }
    if (showOnlyOA && !paper.is_oa) return false;
    if (hideLowRelevance && hasScoredPapers && paper.relevance_score !== undefined && paper.relevance_score < 4) return false;
    return true;
  };
  
  // Filtered papers count - always show all papers when no filters active
  const filteredPapers = reviewQueue ? reviewQueue.filter(filterPaper) : [];
  const hasActiveFilters = sourceFilter !== 'all' || dateFilter !== 'all' || showOnlyOA || hideLowRelevance || showOnlyCollection;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold">Topic not found</h2>
        <Button asChild className="mt-4">
          <Link href="/topics">Back to Topics</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/topics">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{topic.name}</h1>
          {topic.description && (
            <p className="text-muted-foreground mt-1">{topic.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => toggleMutation.mutate({ id: topic.id, is_active: !topic.is_active })}
          >
            {topic.is_active ? (
              <>
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Resume
              </>
            )}
          </Button>
          <Button onClick={runTopic} disabled={isRunning || isRunningHistorical}>
            {isRunning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" />
                Find Papers
              </>
            )}
          </Button>
          {/* Historical Search - one-time only */}
          {!topic.historical_search_done && (
            <Button 
              variant="outline" 
              onClick={runHistoricalSearch} 
              disabled={isRunningHistorical || isRunning}
              title="One-time search for all past papers (no date limit)"
            >
              {isRunningHistorical ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Fetching All...
                </>
              ) : (
                <>
                  <History className="mr-2 h-4 w-4" />
                  Get Past Papers
                </>
              )}
            </Button>
          )}
          <Button 
            variant="secondary" 
            onClick={summarizeAll} 
            disabled={isSummarizing || !reviewQueue?.length}
          >
            {isSummarizing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Summarizing...
              </>
            ) : (
              <>
                <Zap className="mr-2 h-4 w-4" />
                AI Summarize
              </>
            )}
          </Button>
          <Button 
            variant="outline" 
            onClick={scoreRelevance} 
            disabled={isScoring || !reviewQueue?.length}
            title="Use AI to score paper relevance and filter noise"
          >
            {isScoring ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Scoring...
              </>
            ) : (
              <>
                <TrendingUp className="mr-2 h-4 w-4" />
                Score Relevance
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Status badges */}
      <div className="flex gap-2">
        <Badge variant={topic.is_active ? "default" : "secondary"}>
          {topic.is_active ? "Active" : "Paused"}
        </Badge>
        <Badge variant="outline">{topic.frequency}</Badge>
        {topic.last_run_at && (
          <Badge variant="outline">
            <Calendar className="mr-1 h-3 w-3" />
            Last run: {new Date(topic.last_run_at).toLocaleDateString()}
          </Badge>
        )}
      </div>

      {/* Search Progress Banner */}
      {isRunning && (
        <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                <Search className="h-4 w-4 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-blue-900 dark:text-blue-100">Searching for papers...</h3>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  Querying OpenAlex, PubMed, arXiv, Google Scholar, and other sources. This may take a minute.
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-blue-600">Please wait...</p>
              </div>
            </div>
            <Progress className="mt-3 [&>div]:bg-blue-500" />
          </CardContent>
        </Card>
      )}

      {/* Summarizing Progress Banner */}
      {isSummarizing && (
        <Card className="border-purple-200 bg-purple-50 dark:bg-purple-950/20">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
                <Sparkles className="h-4 w-4 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-purple-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-purple-900 dark:text-purple-100">Generating AI summaries...</h3>
                <p className="text-sm text-purple-700 dark:text-purple-300">
                  Analyzing papers and creating concise summaries. This may take a few minutes for many papers.
                </p>
              </div>
            </div>
            <Progress className="mt-3 [&>div]:bg-purple-500" />
          </CardContent>
        </Card>
      )}

      {/* Stats Dashboard */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              <FileText className="inline-block mr-2 h-4 w-4" />
              Total Papers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{stats?.total_papers || reviewQueue?.length || 0}</p>
            <p className="text-xs text-muted-foreground mt-1">
              From {Object.keys(stats?.sources || {}).length || 0} sources
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              <TrendingUp className="inline-block mr-2 h-4 w-4 text-blue-500" />
              New This Week
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-blue-600">{stats?.new_this_week || 0}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Added from latest searches
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              <Sparkles className="inline-block mr-2 h-4 w-4 text-purple-500" />
              AI Summaries
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <p className="text-3xl font-bold text-purple-600">{stats?.with_summaries || 0}</p>
              <p className="text-sm text-muted-foreground">/ {stats?.total_papers || 0}</p>
            </div>
            <Progress value={summaryPercent} className="mt-2 [&>div]:bg-purple-500" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              <BarChart3 className="inline-block mr-2 h-4 w-4 text-green-500" />
              Top Source
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600 capitalize">{stats?.top_source || "—"}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {stats?.top_source_count || 0} papers
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Analytics Row */}
      {(topSources.length > 0 || topCategories.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          {topSources.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Papers by Source
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {topSources.map(([source, count]) => (
                    <div key={source} className="flex items-center justify-between">
                      <span className="text-sm capitalize">{source}</span>
                      <div className="flex items-center gap-2">
                        <Progress 
                          value={(count / (stats?.total_papers || 1)) * 100} 
                          className="w-24 h-2" 
                        />
                        <span className="text-sm font-medium w-8 text-right">{count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          {topCategories.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BookOpen className="h-4 w-4" />
                  Top Categories
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {topCategories.map(([category, count]) => (
                    <Badge key={category} variant="secondary" className="text-xs">
                      {category} ({count})
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Weekly AI Digest */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Newspaper className="h-5 w-5" />
              Weekly AI Digest
            </CardTitle>
            <CardDescription>
              AI-generated narrative summary of your research papers
            </CardDescription>
          </div>
          <Button 
            onClick={generateDigest} 
            disabled={isGeneratingDigest || !reviewQueue?.length}
            variant={digest ? "outline" : "default"}
          >
            {isGeneratingDigest ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                {digest ? "Regenerate Digest" : "Generate Digest"}
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {digest ? (
            <div className="space-y-4">
              {/* Digest Stats */}
              <div className="flex flex-wrap gap-2 pb-3 border-b">
                <Badge variant="outline">
                  {digest.stats?.total || 0} papers analyzed
                </Badge>
                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                  {digest.stats?.high_relevance || 0} high relevance
                </Badge>
                {digest.stats?.sources && Object.entries(digest.stats.sources).map(([source, count]) => (
                  <Badge key={source} variant="secondary" className="text-xs capitalize">
                    {source}: {count as number}
                  </Badge>
                ))}
              </div>
              
              {/* Digest Content */}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <div 
                  dangerouslySetInnerHTML={{ 
                    __html: digest.digest
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\*(.*?)\*/g, '<em>$1</em>')
                      .replace(/^## (.*$)/gim, '<h2 class="text-lg font-semibold mt-4 mb-2">$1</h2>')
                      .replace(/^### (.*$)/gim, '<h3 class="text-md font-medium mt-3 mb-1">$1</h3>')
                      .replace(/^- (.*$)/gim, '<li class="ml-4">$1</li>')
                      .replace(/\n/g, '<br/>')
                  }} 
                />
              </div>
              
              {/* Highlights */}
              {digest.highlights && digest.highlights.length > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Top Highlights
                  </h4>
                  <div className="space-y-2">
                    {digest.highlights.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <Badge variant="outline" className="bg-green-50 text-green-700">
                          {h.score}/10
                        </Badge>
                        <span className="text-muted-foreground line-clamp-1">{h.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Newspaper className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Click "Generate Digest" to create an AI-powered summary of your papers.</p>
              <p className="text-sm mt-1">The digest highlights key findings, trends, and research gaps.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Search Queries */}
      <Card>
        <CardHeader>
          <CardTitle>Search Queries</CardTitle>
          <CardDescription>
            Queries used to find relevant papers from different sources
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Object.entries(topic.queries || {}).map(([source, query]) => (
              <div key={source} className="border rounded-lg p-4">
                <h4 className="font-medium capitalize mb-2">{source}</h4>
                <code className="text-sm bg-muted px-2 py-1 rounded block whitespace-pre-wrap">
                  {query}
                </code>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Enhanced Paper Cards */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Research Papers
              {includedCount > 0 && (
                <Badge variant="default" className="bg-green-600">
                  <Library className="h-3 w-3 mr-1" />
                  {includedCount} in collection
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              {totalVisible} papers • {pendingCount} pending review • {includedCount} in collection
              {stats?.avg_relevance_score && ` • Avg relevance: ${stats.avg_relevance_score.toFixed(1)}/10`}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {/* Collection filter */}
            {includedCount > 0 && (
              <Button 
                variant={showOnlyCollection ? "default" : "outline"} 
                size="sm"
                onClick={() => setShowOnlyCollection(!showOnlyCollection)}
                className={showOnlyCollection ? "bg-green-600 hover:bg-green-700" : ""}
              >
                <Library className="h-4 w-4 mr-1" />
                {showOnlyCollection ? "Collection" : "View Collection"}
              </Button>
            )}
            
            {/* Smart Filters Toggle */}
            <Button
              variant={showFilters ? "default" : "outline"}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="h-4 w-4 mr-1" />
              Filters
              {(sourceFilter !== 'all' || dateFilter !== 'all' || showOnlyOA || hideLowRelevance) && (
                <Badge variant="secondary" className="ml-1 h-5 w-5 p-0 flex items-center justify-center text-xs">
                  {[sourceFilter !== 'all', dateFilter !== 'all', showOnlyOA, hideLowRelevance].filter(Boolean).length}
                </Badge>
              )}
            </Button>
          </div>
        </CardHeader>
        
        {/* Smart Filters Panel */}
        {showFilters && (
          <div className="px-6 pb-4 border-b">
            <div className="flex flex-wrap gap-4 items-center">
              {/* Source Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Source:</label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="text-sm border rounded-md px-2 py-1 bg-background"
                >
                  <option value="all">All Sources</option>
                  {stats?.sources && Object.keys(stats.sources).map((source) => (
                    <option key={source} value={source}>
                      {source.charAt(0).toUpperCase() + source.slice(1)} ({stats.sources[source]})
                    </option>
                  ))}
                </select>
              </div>
              
              {/* Date Filter */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground">Date:</label>
                <select
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  className="text-sm border rounded-md px-2 py-1 bg-background"
                >
                  <option value="all">All Time</option>
                  <option value="week">Last Week</option>
                  <option value="month">Last Month</option>
                  <option value="3months">Last 3 Months</option>
                  <option value="year">Last Year</option>
                </select>
              </div>
              
              {/* Open Access Filter */}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={showOnlyOA}
                  onChange={(e) => setShowOnlyOA(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <Unlock className="h-3 w-3 text-green-600" />
                <span className="text-muted-foreground">Open Access only</span>
              </label>
              
              {/* Relevance filter */}
              {hasScoredPapers && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hideLowRelevance}
                    onChange={(e) => setHideLowRelevance(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <span className="text-muted-foreground">Hide low relevance (&lt;4)</span>
                </label>
              )}
              
              {/* Clear Filters */}
              {(sourceFilter !== 'all' || dateFilter !== 'all' || showOnlyOA || hideLowRelevance) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSourceFilter('all');
                    setDateFilter('all');
                    setShowOnlyOA(false);
                    setHideLowRelevance(false);
                  }}
                  className="text-muted-foreground"
                >
                  <X className="h-3 w-3 mr-1" />
                  Clear all
                </Button>
              )}
            </div>
          </div>
        )}
        <CardContent>
          {/* Filter results count */}
          {hasActiveFilters && filteredPapers.length > 0 && (
            <div className="mb-4 text-sm text-muted-foreground flex items-center gap-2">
              <Filter className="h-3 w-3" />
              Showing {filteredPapers.length} of {reviewQueue?.length || 0} papers
            </div>
          )}
          
          {reviewQueue && reviewQueue.length > 0 ? (
            filteredPapers.length > 0 ? (
            <div className="space-y-4">
              {filteredPapers
                .slice(0, showOnlyCollection ? 50 : 8)
                .map((paper: Paper) => (
                <div
                  key={paper.id}
                  className={`border rounded-lg p-4 hover:bg-muted/30 transition-colors ${
                    paper.included === true ? 'border-green-300 bg-green-50/50 dark:bg-green-950/20' :
                    paper.reviewed_at && !paper.included ? 'opacity-50 border-gray-300' :
                    paper.relevance_score !== undefined && paper.relevance_score < 4 ? 'opacity-60 border-red-200' : ''
                  }`}
                >
                  {/* Paper Header */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-primary hover:underline line-clamp-2 flex items-center gap-2"
                      >
                        {paper.title}
                        <ExternalLink className="h-3 w-3 flex-shrink-0" />
                      </a>
                      <p className="text-sm text-muted-foreground mt-1">
                        {paper.authors?.slice(0, 3).join(", ")}
                        {paper.authors && paper.authors.length > 3 && " et al."}
                      </p>
                    </div>
                    
                    {/* Quick Include/Exclude Buttons */}
                    <div className="flex items-center gap-1">
                      <Button
                        variant={paper.included ? "default" : "outline"}
                        size="sm"
                        onClick={() => handlePaperReview(paper.id, true)}
                        className={paper.included ? "bg-green-600 hover:bg-green-700 h-8 w-8 p-0" : "h-8 w-8 p-0 hover:bg-green-100 hover:border-green-300"}
                        title="Add to collection"
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        variant={paper.reviewed_at && !paper.included ? "default" : "outline"}
                        size="sm"
                        onClick={() => handlePaperReview(paper.id, false)}
                        className={paper.reviewed_at && !paper.included ? "bg-red-600 hover:bg-red-700 h-8 w-8 p-0" : "h-8 w-8 p-0 hover:bg-red-100 hover:border-red-300"}
                        title="Exclude from collection"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  {/* Badges Row */}
                  <div className="flex items-center gap-2 mt-2">
                    {paper.relevance_score !== undefined && paper.relevance_score !== null && (
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${
                          paper.relevance_score >= 7 ? 'bg-green-100 text-green-700 border-green-300' :
                          paper.relevance_score >= 4 ? 'bg-yellow-100 text-yellow-700 border-yellow-300' :
                          'bg-red-100 text-red-700 border-red-300'
                        }`}
                        title={paper.ai_relevance_reason || 'Relevance score'}
                      >
                        {paper.relevance_score}/10
                      </Badge>
                    )}
                    {paper.is_oa && (
                      <Badge variant="secondary" className="text-xs bg-green-100 text-green-700">
                        <Unlock className="h-3 w-3 mr-1" />
                        Open Access
                      </Badge>
                    )}
                    <Badge variant="outline" className="text-xs capitalize">
                      {paper.source}
                    </Badge>
                    {paper.published_date && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(paper.published_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  {/* AI Relevance Reason (if scored low) */}
                  {paper.relevance_score !== undefined && paper.relevance_score < 4 && paper.ai_relevance_reason && (
                    <div className="mt-2 p-2 bg-red-50 dark:bg-red-950/30 rounded-md border border-red-200 dark:border-red-800">
                      <p className="text-xs text-red-600 dark:text-red-400">
                        ⚠️ Low relevance: {paper.ai_relevance_reason}
                      </p>
                    </div>
                  )}

                  {/* AI Summary (if available) */}
                  {paper.summary && (
                    <div className="mt-3 p-3 bg-purple-50 dark:bg-purple-950/30 rounded-md border border-purple-200 dark:border-purple-800">
                      <div className="flex items-center gap-2 text-xs text-purple-600 dark:text-purple-400 font-medium mb-1">
                        <Sparkles className="h-3 w-3" />
                        AI Summary
                        {paper.headline && <span className="text-purple-800 dark:text-purple-300">• {paper.headline}</span>}
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-3">{paper.summary}</p>
                    </div>
                  )}

                  {/* Paper Meta - DOI only */}
                  {paper.doi && (
                    <div className="mt-2">
                      <a 
                        href={`https://doi.org/${paper.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline"
                      >
                        DOI: {paper.doi}
                      </a>
                    </div>
                  )}
                </div>
              ))}
              {!showOnlyCollection && filteredPapers.length > 8 && (
                <div className="text-center pt-2">
                  <Button variant="outline" asChild>
                    <Link href={`/topics/${topic.id}/papers`}>
                      View all {filteredPapers.length} papers
                    </Link>
                  </Button>
                </div>
              )}
            </div>
            ) : (
              <div className="text-center py-8">
                <Filter className="h-8 w-8 mx-auto text-muted-foreground/50 mb-3" />
                <h3 className="text-md font-medium">No papers match your filters</h3>
                <p className="text-muted-foreground text-sm mt-1">
                  Try adjusting or clearing your filters to see more results.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => {
                    setSourceFilter('all');
                    setDateFilter('all');
                    setShowOnlyOA(false);
                    setHideLowRelevance(false);
                    setShowOnlyCollection(false);
                  }}
                >
                  Clear all filters
                </Button>
              </div>
            )
          ) : (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium">No papers found yet</h3>
              <p className="text-muted-foreground mt-1">
                Click "Find Papers" to search for academic papers matching your queries.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button variant="outline" asChild>
            <Link href={`/topics/${topic.id}/edit`}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit Topic
            </Link>
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (confirm("Are you sure you want to delete this topic? This cannot be undone.")) {
                deleteMutation.mutate(topic.id);
              }
            }}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete Topic
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
