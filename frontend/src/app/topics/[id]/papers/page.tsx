"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { topicsApi, Topic } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  ArrowLeft, 
  ExternalLink,
  Check,
  X,
  Loader2,
  Filter,
  Search
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useState } from "react";

type FilterType = "all" | "pending" | "included" | "excluded";

export default function PapersPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const topicId = params.id as string;
  const [filter, setFilter] = useState<FilterType>("all");

  const { data: topic, isLoading: topicLoading } = useQuery({
    queryKey: ["topic", topicId],
    queryFn: async () => {
      const response = await topicsApi.get(topicId);
      return response.data as Topic;
    },
  });

  const { data: papers, isLoading: papersLoading } = useQuery({
    queryKey: ["review-queue", topicId],
    queryFn: async () => {
      const response = await topicsApi.getReviewQueue(topicId);
      return response.data;
    },
    enabled: !!topicId,
  });

  const reviewMutation = useMutation({
    mutationFn: async ({ paperId, included }: { paperId: string; included: boolean }) => {
      return await topicsApi.reviewPaper(topicId, paperId, included);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-queue", topicId] });
      toast.success("Paper reviewed");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to review paper");
    },
  });

  const isLoading = topicLoading || papersLoading;

  const filteredPapers = papers?.filter((paper: any) => {
    switch (filter) {
      case "pending":
        return !paper.reviewed_at;
      case "included":
        return paper.included === true;
      case "excluded":
        return paper.reviewed_at && paper.included === false;
      default:
        return true;
    }
  });

  const counts = {
    all: papers?.length || 0,
    pending: papers?.filter((p: any) => !p.reviewed_at).length || 0,
    included: papers?.filter((p: any) => p.included === true).length || 0,
    excluded: papers?.filter((p: any) => p.reviewed_at && p.included === false).length || 0,
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-center text-muted-foreground">Topic not found</p>
        <div className="flex justify-center mt-4">
          <Button variant="outline" asChild>
            <Link href="/topics">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Topics
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/topics/${topic.id}`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Papers</h1>
          <p className="text-muted-foreground">{topic.name}</p>
        </div>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-2">
            {(["all", "pending", "included", "excluded"] as FilterType[]).map((f) => (
              <Button
                key={f}
                variant={filter === f ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(f)}
              >
                <span className="capitalize">{f}</span>
                <Badge variant="secondary" className="ml-2">
                  {counts[f]}
                </Badge>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Papers List */}
      <div className="space-y-4">
        {filteredPapers && filteredPapers.length > 0 ? (
          filteredPapers.map((paper: any) => (
            <Card key={paper.id} className="overflow-hidden">
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  {/* Paper Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="font-semibold text-lg leading-tight mb-2">
                          {paper.title}
                        </h3>
                        <p className="text-sm text-muted-foreground mb-2">
                          {paper.authors?.join(", ") || "Unknown authors"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {paper.reviewed_at ? (
                          <Badge variant={paper.included ? "default" : "destructive"}>
                            {paper.included ? "Included" : "Excluded"}
                          </Badge>
                        ) : (
                          <Badge variant="secondary">Pending</Badge>
                        )}
                      </div>
                    </div>

                    {paper.abstract && (
                      <p className="text-sm text-muted-foreground mb-4 line-clamp-3">
                        {paper.abstract}
                      </p>
                    )}

                    <div className="flex items-center gap-4 text-sm">
                      <Badge variant="outline" className="capitalize">
                        {paper.source}
                      </Badge>
                      {paper.published_date && (
                        <span className="text-muted-foreground">
                          Published: {new Date(paper.published_date).toLocaleDateString()}
                        </span>
                      )}
                      {paper.url && (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline flex items-center gap-1"
                        >
                          <ExternalLink className="h-3 w-3" />
                          View Paper
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2 mt-4 pt-4 border-t">
                  <Button
                    variant={paper.included === false ? "destructive" : "outline"}
                    size="sm"
                    onClick={() => reviewMutation.mutate({ paperId: paper.id, included: false })}
                    disabled={reviewMutation.isPending}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Exclude
                  </Button>
                  <Button
                    variant={paper.included === true ? "default" : "outline"}
                    size="sm"
                    onClick={() => reviewMutation.mutate({ paperId: paper.id, included: true })}
                    disabled={reviewMutation.isPending}
                  >
                    <Check className="h-4 w-4 mr-1" />
                    Include
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          <Card>
            <CardContent className="py-12 text-center">
              <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                {filter === "all"
                  ? "No papers found yet. Run a search to find papers."
                  : `No ${filter} papers.`}
              </p>
              {filter === "all" && (
                <Button variant="outline" className="mt-4" asChild>
                  <Link href={`/topics/${topic.id}`}>
                    Go to Topic
                  </Link>
                </Button>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
