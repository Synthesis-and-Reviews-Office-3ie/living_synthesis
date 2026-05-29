"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, BookOpen, Users, FileCheck, Loader2, ExternalLink } from "lucide-react";
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
}

export default function ReviewsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  const { data: reviews, isLoading } = useQuery({
    queryKey: ["living-reviews"],
    queryFn: async () => {
      const response = await api.get("/reviews");
      return response.data as LivingReview[];
    },
    enabled: !!user,
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

  if (!user) {
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
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Living Reviews</h1>
            <p className="text-muted-foreground">
              Manage your living systematic reviews and evidence gap maps
            </p>
          </div>
          <Button asChild>
            <Link href="/reviews/new">
              <Plus className="mr-2 h-4 w-4" />
              New Review
            </Link>
          </Button>
        </div>

        {/* Reviews List */}
        {!reviews || reviews.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="font-semibold text-lg mb-2">No living reviews yet</h3>
              <p className="text-muted-foreground text-center mb-4 max-w-md">
                Create a living systematic review to automatically track new evidence 
                and keep your review up-to-date with the latest research.
              </p>
              <Button asChild>
                <Link href="/reviews/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Living Review
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {reviews.map((review) => (
              <Link key={review.id} href={`/reviews/${review.id}`}>
                <Card className="hover:border-primary transition-colors cursor-pointer">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CardTitle className="text-lg">{review.title}</CardTitle>
                        <Badge variant={statusColors[review.status]}>
                          {review.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>v{review.current_version}</span>
                      </div>
                    </div>
                    {review.description && (
                      <CardDescription className="line-clamp-2">
                        {review.description}
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-6 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <FileCheck className="h-4 w-4" />
                        <span>
                          {review.screened_papers}/{review.total_papers} screened
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <BookOpen className="h-4 w-4" />
                        <span>{review.included_papers} included</span>
                      </div>
                      <div className="ml-auto">
                        Updated {new Date(review.updated_at).toLocaleDateString()}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}

        {/* Info Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              What is a Living Review?
            </CardTitle>
          </CardHeader>
          <CardContent className="prose prose-sm max-w-none text-muted-foreground">
            <p>
              A living systematic review is a continuously updated review that incorporates 
              relevant new evidence as it becomes available. Instead of being static snapshots 
              in time, living reviews evolve with the evidence base.
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>Automatic monitoring of new publications</li>
              <li>Dual screening with conflict resolution</li>
              <li>Version tracking and PRISMA flow generation</li>
              <li>Team collaboration with role-based access</li>
              <li>Public landing pages for sharing</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
