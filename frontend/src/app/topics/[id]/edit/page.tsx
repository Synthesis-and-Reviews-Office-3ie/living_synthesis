"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { topicsApi, Topic } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Loader2, BookOpen, Crown } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

const SOURCES = [
  { key: "openalex", label: "OpenAlex", placeholder: '("systematic review") AND ("LLM")' },
  { key: "pubmed", label: "PubMed", placeholder: '("systematic review"[Title/Abstract]) AND ("AI"[Title/Abstract])' },
  { key: "arxiv", label: "arXiv", placeholder: '"systematic review" AND "machine learning"' },
];

const LIVING_REVIEW_TYPES = [
  { value: "systematic_review", label: "Systematic Review" },
  { value: "evidence_gap_map", label: "Evidence Gap Map" },
  { value: "meta_analysis", label: "Meta-Analysis" },
  { value: "scoping_review", label: "Scoping Review" },
];

export default function EditTopicPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const topicId = params.id as string;
  
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("weekly");
  const [queries, setQueries] = useState<Record<string, string>>({});
  const [isActive, setIsActive] = useState(true);
  
  // Living Review fields
  const [livingReviewEnabled, setLivingReviewEnabled] = useState(false);
  const [livingReviewType, setLivingReviewType] = useState("");
  const [livingReviewSource, setLivingReviewSource] = useState("");

  const { data: topic, isLoading } = useQuery({
    queryKey: ["topic", topicId],
    queryFn: async () => {
      const response = await topicsApi.get(topicId);
      return response.data as Topic;
    },
  });

  // Initialize form when topic loads
  useEffect(() => {
    if (topic) {
      setName(topic.name);
      setDescription(topic.description || "");
      setFrequency(topic.frequency || "weekly");
      setQueries(topic.queries || {});
      setIsActive(topic.is_active);
      setLivingReviewEnabled(topic.living_review_enabled || false);
      setLivingReviewType(topic.living_review_type || "");
      setLivingReviewSource(topic.living_review_source || "");
    }
  }, [topic]);

  const canUsePremium = user?.tier === "pro" || user?.tier === "team";

  const updateMutation = useMutation({
    mutationFn: () =>
      topicsApi.update(topicId, {
        name,
        description: description || undefined,
        queries: Object.fromEntries(
          Object.entries(queries).filter(([_, v]) => v.trim())
        ),
        frequency,
        is_active: isActive,
        living_review_enabled: livingReviewEnabled,
        living_review_type: livingReviewType || undefined,
        living_review_source: livingReviewSource || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topic", topicId] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      toast.success("Topic updated successfully!");
      router.push(`/topics/${topicId}`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to update topic");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const filledQueries = Object.values(queries).filter((q) => q.trim());
    if (filledQueries.length === 0) {
      toast.error("Please add at least one search query");
      return;
    }
    
    updateMutation.mutate();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Topic not found</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link href="/topics">Back to Topics</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Link href={`/topics/${topicId}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Edit Topic</h1>
          <p className="text-muted-foreground">
            Update your research topic settings
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Topic Name *</Label>
              <Input
                id="name"
                placeholder="e.g., LLMs in Evidence Synthesis"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                placeholder="A brief description of this topic"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span>Active</span>
                </label>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Frequency</Label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="frequency"
                    value="weekly"
                    checked={frequency === "weekly"}
                    onChange={() => setFrequency("weekly")}
                    className="w-4 h-4"
                  />
                  <span>Weekly</span>
                </label>
                <label className={`flex items-center gap-2 ${canUsePremium ? "cursor-pointer" : "opacity-50 cursor-not-allowed"}`}>
                  <input
                    type="radio"
                    name="frequency"
                    value="daily"
                    checked={frequency === "daily"}
                    onChange={() => canUsePremium && setFrequency("daily")}
                    disabled={!canUsePremium}
                    className="w-4 h-4"
                  />
                  <span>Daily</span>
                  {!canUsePremium && (
                    <span className="text-xs text-muted-foreground">(Pro+)</span>
                  )}
                </label>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Search Queries</CardTitle>
            <CardDescription>
              Define search queries for each source. At least one query is required.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {SOURCES.map((source) => (
              <div key={source.key} className="space-y-2">
                <Label htmlFor={source.key}>{source.label}</Label>
                <Input
                  id={source.key}
                  placeholder={source.placeholder}
                  value={queries[source.key] || ""}
                  onChange={(e) =>
                    setQueries((prev) => ({ ...prev, [source.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Living Review Section */}
        <Card className={!canUsePremium ? "opacity-75" : ""}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Living Review
              <Badge variant="secondary" className="ml-2">
                <Crown className="h-3 w-3 mr-1" />
                Pro
              </Badge>
            </CardTitle>
            <CardDescription>
              Link this topic to an existing systematic review or evidence gap map to enable "living updates".
              New papers matching your search will be flagged for potential inclusion.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!canUsePremium ? (
              <div className="text-center py-4">
                <p className="text-sm text-muted-foreground mb-2">
                  Living Review is a premium feature. Upgrade to Pro to enable it.
                </p>
                <Button variant="outline" size="sm" asChild>
                  <Link href="/settings">Upgrade to Pro</Link>
                </Button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="livingReviewEnabled"
                    checked={livingReviewEnabled}
                    onChange={(e) => setLivingReviewEnabled(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <Label htmlFor="livingReviewEnabled" className="cursor-pointer">
                    Enable Living Review for this topic
                  </Label>
                </div>
                
                {livingReviewEnabled && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="livingReviewType">Review Type</Label>
                      <select
                        id="livingReviewType"
                        value={livingReviewType}
                        onChange={(e) => setLivingReviewType(e.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <option value="">Select type...</option>
                        {LIVING_REVIEW_TYPES.map((type) => (
                          <option key={type.value} value={type.value}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="livingReviewSource">Original Review URL or Reference</Label>
                      <Textarea
                        id="livingReviewSource"
                        placeholder="Paste the URL to your published review, DOI, or description of the original review"
                        value={livingReviewSource}
                        onChange={(e) => setLivingReviewSource(e.target.value)}
                        rows={3}
                      />
                      <p className="text-xs text-muted-foreground">
                        This helps link new papers to your original review for living updates.
                      </p>
                    </div>
                  </>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <div className="flex gap-4">
          <Button
            type="submit"
            disabled={!name.trim() || updateMutation.isPending}
          >
            {updateMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Changes
          </Button>
          <Button type="button" variant="outline" asChild>
            <Link href={`/topics/${topicId}`}>Cancel</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
