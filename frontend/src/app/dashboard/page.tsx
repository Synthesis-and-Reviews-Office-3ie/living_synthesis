"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { topicsApi, Topic, api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, FileText, Mail, TrendingUp, Loader2, BookOpen, Users, ClipboardList, Trash2, Pencil } from "lucide-react";
import Link from "next/link";

interface LivingReview {
  id: string;
  title: string;
  slug: string;
  description?: string;
  status: "draft" | "active" | "paused" | "completed" | "archived";
  current_version: number;
  total_papers: number;
  screened_papers: number;
  included_papers: number;
  created_at: string;
  updated_at: string;
  owner_id?: string;
}

interface MyAssignment {
  id: string;
  paper_id: string;
  paper_title: string | null;
  status: string;
  living_review_id: string;
}

export default function DashboardPage() {
  const { user, loading, accessToken } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [deletingReview, setDeletingReview] = useState<string | null>(null);
  const [deletingTopic, setDeletingTopic] = useState<string | null>(null);

  // Debug log
  useEffect(() => {
    console.log("[Dashboard] Auth state:", { user: !!user, loading, accessToken: !!accessToken });
  }, [user, loading, accessToken]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  const { data: topicsData } = useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      const response = await topicsApi.list();
      return response.data as Topic[];
    },
    enabled: !!user,
  });

  // Fetch living reviews
  const { data: reviewsData, error: reviewsError, isLoading: reviewsLoading } = useQuery({
    queryKey: ["living-reviews"],
    queryFn: async () => {
      console.log("[Dashboard] Fetching living reviews...");
      const response = await api.get("/reviews");
      console.log("[Dashboard] Living reviews response:", response.data);
      return response.data as LivingReview[];
    },
    enabled: !!user,
    retry: 1,
  });

  // Debug log
  useEffect(() => {
    if (reviewsError) {
      console.error("[Dashboard] Reviews fetch error:", reviewsError);
    }
  }, [reviewsError]);

  // Delete review handler
  const handleDeleteReview = async (reviewId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this review? This action cannot be undone.")) {
      return;
    }
    
    setDeletingReview(reviewId);
    try {
      await api.delete(`/reviews/${reviewId}`);
      queryClient.invalidateQueries({ queryKey: ["living-reviews"] });
    } catch (error) {
      console.error("Failed to delete review:", error);
      alert("Failed to delete review. Please try again.");
    } finally {
      setDeletingReview(null);
    }
  };

  // Delete topic handler
  const handleDeleteTopic = async (topicId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this topic? This action cannot be undone.")) {
      return;
    }
    
    setDeletingTopic(topicId);
    try {
      await topicsApi.delete(topicId);
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    } catch (error) {
      console.error("Failed to delete topic:", error);
      alert("Failed to delete topic. Please try again.");
    } finally {
      setDeletingTopic(null);
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Don't render if no user (will redirect)
  if (!user) {
    return null;
  }

  const topics = topicsData || [];
  const activeTopics = topics.filter((t) => t.is_active);
  const reviews = reviewsData || [];
  const activeReviews = reviews.filter((r) => r.status === "active" || r.status === "draft");

  const tierLimits = {
    free: { topics: 1, frequency: ["weekly"] },
    pro: { topics: 3, frequency: ["daily", "weekly"] },
    team: { topics: 10, frequency: ["daily", "weekly"] },
  };

  const limit = tierLimits[user?.tier || "free"];
  const canCreateTopic = topics.length < limit.topics;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {user?.name || user?.email}
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Topics</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeTopics.length}</div>
            <p className="text-xs text-muted-foreground">
              of {limit.topics} available
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Living Reviews</CardTitle>
            <BookOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeReviews.length}</div>
            <p className="text-xs text-muted-foreground">
              {reviews.reduce((sum, r) => sum + (r.total_papers - r.screened_papers), 0)} papers pending
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Your Plan</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{user?.tier}</div>
            {user?.tier === "free" && (
              <Link href="/settings" className="text-xs text-primary hover:underline">
                Upgrade to Pro
              </Link>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Living Reviews Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Your Living Reviews</h2>
          <Button variant="outline" size="sm" asChild>
            <Link href="/reviews/new">
              <Plus className="mr-2 h-4 w-4" />
              New Review
            </Link>
          </Button>
        </div>
        
        {reviews.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-8">
              <BookOpen className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="font-semibold mb-1">No living reviews yet</h3>
              <p className="text-muted-foreground text-center text-sm mb-3">
                Create a living systematic review to track new evidence
              </p>
              <Button size="sm" asChild>
                <Link href="/reviews/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Review
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {reviews.map((review) => {
              const pendingPapers = review.total_papers - review.screened_papers;
              const progressPercent = review.total_papers > 0 
                ? Math.round((review.screened_papers / review.total_papers) * 100) 
                : 0;
              
              return (
                <Link key={review.id} href={`/reviews/${review.id}`}>
                  <Card className="hover:border-primary transition-colors cursor-pointer h-full">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-base line-clamp-2">{review.title}</CardTitle>
                        <Badge 
                          variant={review.status === "active" ? "default" : "secondary"}
                          className="shrink-0"
                        >
                          {review.status}
                        </Badge>
                      </div>
                      {review.description && (
                        <CardDescription className="line-clamp-2 text-xs">
                          {review.description}
                        </CardDescription>
                      )}
                    </CardHeader>
                    <CardContent className="pt-0">
                      {/* Progress Bar */}
                      <div className="mb-3">
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>Screening Progress</span>
                          <span>{progressPercent}%</span>
                        </div>
                        <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-primary transition-all"
                            style={{ width: `${progressPercent}%` }}
                          />
                        </div>
                      </div>
                      
                      {/* Stats */}
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="bg-muted/50 rounded p-2">
                          <div className="text-lg font-bold">{review.total_papers}</div>
                          <div className="text-xs text-muted-foreground">Total</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2">
                          <div className="text-lg font-bold text-amber-600">{pendingPapers}</div>
                          <div className="text-xs text-muted-foreground">Pending</div>
                        </div>
                        <div className="bg-muted/50 rounded p-2">
                          <div className="text-lg font-bold text-green-600">{review.included_papers}</div>
                          <div className="text-xs text-muted-foreground">Included</div>
                        </div>
                      </div>

                      {/* Pending Tasks Alert */}
                      {pendingPapers > 0 && (
                        <div className="mt-3 flex items-center gap-2 text-xs bg-amber-50 text-amber-800 rounded-md p-2 border border-amber-200">
                          <ClipboardList className="h-4 w-4 shrink-0" />
                          <span>{pendingPapers} papers need screening</span>
                        </div>
                      )}

                      {/* Action Buttons */}
                      <div className="mt-3 flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-foreground"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            router.push(`/reviews/${review.id}/edit`);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                          <span className="ml-1">Edit</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={(e) => handleDeleteReview(review.id, e)}
                          disabled={deletingReview === review.id}
                        >
                          {deletingReview === review.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                          <span className="ml-1">Delete</span>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Topics */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Your Topics</h2>
          <Button variant="outline" size="sm" disabled={!canCreateTopic} asChild>
            <Link href="/topics/new">
              <Plus className="mr-2 h-4 w-4" />
              New Topic
            </Link>
          </Button>
        </div>
        {topics.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="font-semibold text-lg mb-2">No topics yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first topic to start receiving AI-curated newsletters
              </p>
              <Button asChild>
                <Link href="/topics/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Topic
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {topics.map((topic) => (
              <Link key={topic.id} href={`/topics/${topic.id}`}>
                <Card className="hover:border-primary transition-colors cursor-pointer">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{topic.name}</CardTitle>
                      <div className="flex gap-2">
                        <Badge variant={topic.is_active ? "default" : "secondary"}>
                          {topic.is_active ? "Active" : "Paused"}
                        </Badge>
                        <Badge variant="outline">{topic.frequency}</Badge>
                      </div>
                    </div>
                    {topic.description && (
                      <CardDescription>{topic.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-muted-foreground">
                        {topic.last_run_at
                          ? `Last run: ${new Date(topic.last_run_at).toLocaleDateString()}`
                          : "Never run"}
                      </p>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-foreground"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            router.push(`/topics/${topic.id}/edit`);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                          <span className="ml-1">Edit</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={(e) => handleDeleteTopic(topic.id, e)}
                          disabled={deletingTopic === topic.id}
                        >
                          {deletingTopic === topic.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                          <span className="ml-1">Delete</span>
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
