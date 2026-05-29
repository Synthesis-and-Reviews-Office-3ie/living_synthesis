"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api, topicsApi, Topic } from "@/lib/api";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

interface LivingReview {
  id: string;
  title: string;
  slug: string;
  description?: string;
  status: "draft" | "active" | "paused" | "completed" | "archived";
  topic_id?: string;
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
  protocol_url?: string;
  publication_doi?: string;
  publication_url?: string;
  is_public?: boolean;
}

const STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

export default function EditReviewPage() {
  const params = useParams();
  const reviewId = params.id as string;
  const { user, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    status: "draft" as string,
    topic_id: "",
    is_public: false,
    // PICO Criteria
    pico_population: "",
    pico_intervention: "",
    pico_comparator: "",
    pico_outcome: "",
    // Registry IDs
    prospero_id: "",
    osf_id: "",
    // Protocol & Publication
    protocol_url: "",
    publication_doi: "",
    publication_url: "",
  });

  // Fetch the review
  const { data: review, isLoading: reviewLoading } = useQuery({
    queryKey: ["living-review", reviewId],
    queryFn: async () => {
      const response = await api.get(`/reviews/${reviewId}`);
      return response.data as LivingReview;
    },
    enabled: !!user && !!reviewId,
  });

  // Fetch user's topics
  const { data: topics } = useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      const response = await topicsApi.list();
      return response.data as Topic[];
    },
    enabled: !!user,
  });

  // Initialize form when review loads
  useEffect(() => {
    if (review) {
      setFormData({
        title: review.title || "",
        description: review.description || "",
        status: review.status || "draft",
        topic_id: review.topic_id || "",
        is_public: review.is_public || false,
        pico_population: review.pico_population || review.population || "",
        pico_intervention: review.pico_intervention || review.intervention || "",
        pico_comparator: review.pico_comparator || review.comparator || "",
        pico_outcome: review.pico_outcome || review.outcomes || "",
        prospero_id: review.prospero_id || "",
        osf_id: review.osf_id || "",
        protocol_url: review.protocol_url || "",
        publication_doi: review.publication_doi || "",
        publication_url: review.publication_url || "",
      });
    }
  }, [review]);

  const updateMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const response = await api.put(`/reviews/${reviewId}`, {
        title: data.title,
        description: data.description || null,
        status: data.status,
        topic_id: data.topic_id || null,
        is_public: data.is_public,
        pico_population: data.pico_population || null,
        pico_intervention: data.pico_intervention || null,
        pico_comparator: data.pico_comparator || null,
        pico_outcome: data.pico_outcome || null,
        prospero_id: data.prospero_id || null,
        osf_id: data.osf_id || null,
        protocol_url: data.protocol_url || null,
        publication_doi: data.publication_doi || null,
        publication_url: data.publication_url || null,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["living-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["living-reviews"] });
      toast.success("Review updated successfully!");
      router.push(`/reviews/${reviewId}`);
    },
    onError: (error: any) => {
      const errorDetail = error.response?.data?.detail || "Failed to update review";
      if (errorDetail.toLowerCase().includes("invalid token") || error.response?.status === 401) {
        toast.error("Your session has expired. Please log out and log back in.");
      } else {
        toast.error(errorDetail);
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      toast.error("Title is required");
      return;
    }
    updateMutation.mutate(formData);
  };

  if (loading || reviewLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </DashboardLayout>
    );
  }

  if (!user) {
    router.push("/login");
    return null;
  }

  if (!review) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground">Review not found</p>
          <Button variant="outline" className="mt-4" asChild>
            <Link href="/reviews">Back to Reviews</Link>
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/reviews/${reviewId}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Edit Living Review</h1>
            <p className="text-muted-foreground">
              Update your living review settings
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>
                Update the title and description of your review
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title *</Label>
                <Input
                  id="title"
                  placeholder="e.g., Living systematic review of climate change impacts on mortality"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Brief description of your review's scope and objectives..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="status">Status</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value) => setFormData({ ...formData, status: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="is_public">Visibility</Label>
                  <Select
                    value={formData.is_public ? "public" : "private"}
                    onValueChange={(value) => setFormData({ ...formData, is_public: value === "public" })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select visibility" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="private">Private</SelectItem>
                      <SelectItem value="public">Public</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Topic Linkage */}
          <Card>
            <CardHeader>
              <CardTitle>Search Configuration</CardTitle>
              <CardDescription>
                Link this review to a Topic to get papers for screening
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="topic">Linked Topic</Label>
                <Select
                  value={formData.topic_id || "none"}
                  onValueChange={(value) => setFormData({ ...formData, topic_id: value === "none" ? "" : value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a topic to link..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No topic linked</SelectItem>
                    {topics?.map((topic) => (
                      <SelectItem key={topic.id} value={topic.id}>
                        {topic.name} ({topic.papers_count || 0} papers)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground">
                  Papers from this topic will appear in your screening queue
                </p>
              </div>
            </CardContent>
          </Card>

          {/* PICO Criteria */}
          <Card>
            <CardHeader>
              <CardTitle>PICO Criteria</CardTitle>
              <CardDescription>
                Define inclusion criteria for screening papers. These will be used to 
                guide both manual and AI-assisted screening.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="pico_population">Population</Label>
                <Textarea
                  id="pico_population"
                  placeholder="e.g., Adults aged 18+ in low and middle income countries"
                  value={formData.pico_population}
                  onChange={(e) => setFormData({ ...formData, pico_population: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pico_intervention">Intervention</Label>
                <Textarea
                  id="pico_intervention"
                  placeholder="e.g., Cash transfer programs, conditional or unconditional"
                  value={formData.pico_intervention}
                  onChange={(e) => setFormData({ ...formData, pico_intervention: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pico_comparator">Comparator</Label>
                <Textarea
                  id="pico_comparator"
                  placeholder="e.g., No intervention, alternative programs, or business as usual"
                  value={formData.pico_comparator}
                  onChange={(e) => setFormData({ ...formData, pico_comparator: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pico_outcome">Outcomes</Label>
                <Textarea
                  id="pico_outcome"
                  placeholder="e.g., School enrollment, educational attainment, health outcomes"
                  value={formData.pico_outcome}
                  onChange={(e) => setFormData({ ...formData, pico_outcome: e.target.value })}
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>

          {/* Registry IDs */}
          <Card>
            <CardHeader>
              <CardTitle>Protocol Registration</CardTitle>
              <CardDescription>
                Link to your registered protocol (optional but recommended)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="prospero_id">PROSPERO ID</Label>
                  <Input
                    id="prospero_id"
                    placeholder="CRD42024XXXXXX"
                    value={formData.prospero_id}
                    onChange={(e) => setFormData({ ...formData, prospero_id: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="osf_id">OSF Registration</Label>
                  <Input
                    id="osf_id"
                    placeholder="osf.io/xxxxx"
                    value={formData.osf_id}
                    onChange={(e) => setFormData({ ...formData, osf_id: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="protocol_url">Protocol URL</Label>
                <Input
                  id="protocol_url"
                  type="url"
                  placeholder="https://..."
                  value={formData.protocol_url}
                  onChange={(e) => setFormData({ ...formData, protocol_url: e.target.value })}
                />
              </div>
            </CardContent>
          </Card>

          {/* Publication */}
          <Card>
            <CardHeader>
              <CardTitle>Publication</CardTitle>
              <CardDescription>
                Link to published versions of this review
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="publication_doi">Publication DOI</Label>
                  <Input
                    id="publication_doi"
                    placeholder="10.xxxx/xxxxx"
                    value={formData.publication_doi}
                    onChange={(e) => setFormData({ ...formData, publication_doi: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="publication_url">Publication URL</Label>
                  <Input
                    id="publication_url"
                    type="url"
                    placeholder="https://..."
                    value={formData.publication_url}
                    onChange={(e) => setFormData({ ...formData, publication_url: e.target.value })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Submit */}
          <div className="flex justify-end gap-4">
            <Button variant="outline" asChild>
              <Link href={`/reviews/${reviewId}`}>Cancel</Link>
            </Button>
            <Button 
              type="submit" 
              disabled={!formData.title.trim() || updateMutation.isPending}
            >
              {updateMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save Changes
            </Button>
          </div>

          {updateMutation.isError && (
            <p className="text-sm text-red-500 text-center">
              Failed to update review. Please try again.
            </p>
          )}
        </form>
      </div>
    </DashboardLayout>
  );
}
