"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api, topicsApi, Topic } from "@/lib/api";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function NewReviewPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    topic_id: "", // Link to topic for papers
    // PICO Criteria
    population: "",
    intervention: "",
    comparator: "",
    outcomes: "",
    // Registry IDs
    prospero_id: "",
    osf_id: "",
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

  const createMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const response = await api.post("/reviews", {
        title: data.title,
        description: data.description || null,
        topic_id: data.topic_id || null,
        population: data.population || null,
        intervention: data.intervention || null,
        comparator: data.comparator || null,
        outcomes: data.outcomes || null,
        prospero_id: data.prospero_id || null,
        osf_id: data.osf_id || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["living-reviews"] });
      router.push(`/reviews/${data.id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    createMutation.mutate(formData);
  };

  if (loading) {
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

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/reviews">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Create Living Review</h1>
            <p className="text-muted-foreground">
              Set up a new living systematic review or evidence gap map
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Topic Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Search Configuration</CardTitle>
              <CardDescription>
                Link this review to a Topic to get papers for screening
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!topics || topics.length === 0 ? (
                <div className="flex items-start gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-yellow-800">No Topics Found</p>
                    <p className="text-sm text-yellow-700 mt-1">
                      You need to create a Topic first to define search queries. 
                      Papers from that Topic will be available for screening in this review.
                    </p>
                    <Button variant="outline" size="sm" className="mt-2" asChild>
                      <Link href="/topics/new">Create a Topic</Link>
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label htmlFor="topic">Select Topic *</Label>
                  <Select
                    value={formData.topic_id}
                    onValueChange={(value) => setFormData({ ...formData, topic_id: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a topic to link..." />
                    </SelectTrigger>
                    <SelectContent>
                      {topics.map((topic) => (
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
              )}
            </CardContent>
          </Card>

          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>
                Give your review a title and description
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
                <Label htmlFor="population">Population</Label>
                <Textarea
                  id="population"
                  placeholder="e.g., Adults aged 18+ in low and middle income countries"
                  value={formData.population}
                  onChange={(e) => setFormData({ ...formData, population: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="intervention">Intervention</Label>
                <Textarea
                  id="intervention"
                  placeholder="e.g., Cash transfer programs, conditional or unconditional"
                  value={formData.intervention}
                  onChange={(e) => setFormData({ ...formData, intervention: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="comparator">Comparator</Label>
                <Textarea
                  id="comparator"
                  placeholder="e.g., No intervention, alternative programs, or business as usual"
                  value={formData.comparator}
                  onChange={(e) => setFormData({ ...formData, comparator: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="outcomes">Outcomes</Label>
                <Textarea
                  id="outcomes"
                  placeholder="e.g., School enrollment, educational attainment, health outcomes"
                  value={formData.outcomes}
                  onChange={(e) => setFormData({ ...formData, outcomes: e.target.value })}
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
            </CardContent>
          </Card>

          {/* Submit */}
          <div className="flex justify-end gap-4">
            <Button variant="outline" asChild>
              <Link href="/reviews">Cancel</Link>
            </Button>
            <Button 
              type="submit" 
              disabled={!formData.title.trim() || createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create Review
            </Button>
          </div>

          {createMutation.isError && (
            <p className="text-sm text-red-500 text-center">
              Failed to create review. Please try again.
            </p>
          )}
        </form>
      </div>
    </DashboardLayout>
  );
}
