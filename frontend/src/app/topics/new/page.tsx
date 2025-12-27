"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { topicsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Loader2, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

const SOURCES = [
  { key: "openalex", label: "OpenAlex", placeholder: '("systematic review") AND ("LLM")' },
  { key: "pubmed", label: "PubMed", placeholder: '("systematic review"[Title/Abstract]) AND ("AI"[Title/Abstract])' },
  { key: "google", label: "Google (blogs)", placeholder: '"AI" "evidence synthesis" blog' },
];

export default function NewTopicPage() {
  const router = useRouter();
  const { user } = useAuth();
  
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("weekly");
  const [queries, setQueries] = useState<Record<string, string>>({
    openalex: "",
    pubmed: "",
    google: "",
  });

  const canUseDaily = user?.tier === "pro" || user?.tier === "team";

  const createMutation = useMutation({
    mutationFn: () =>
      topicsApi.create({
        name,
        description: description || undefined,
        queries: Object.fromEntries(
          Object.entries(queries).filter(([_, v]) => v.trim())
        ),
        frequency,
      }),
    onSuccess: () => {
      toast.success("Topic created successfully!");
      router.push("/topics");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create topic");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const filledQueries = Object.values(queries).filter((q) => q.trim());
    if (filledQueries.length === 0) {
      toast.error("Please add at least one search query");
      return;
    }
    
    createMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Link href="/topics">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Create Topic</h1>
          <p className="text-muted-foreground">
            Set up a new research topic for your newsletter
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
                <label className={`flex items-center gap-2 ${canUseDaily ? "cursor-pointer" : "opacity-50 cursor-not-allowed"}`}>
                  <input
                    type="radio"
                    name="frequency"
                    value="daily"
                    checked={frequency === "daily"}
                    onChange={() => canUseDaily && setFrequency("daily")}
                    disabled={!canUseDaily}
                    className="w-4 h-4"
                  />
                  <span>Daily</span>
                  {!canUseDaily && (
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

        <div className="flex gap-4">
          <Button
            type="submit"
            disabled={!name.trim() || createMutation.isPending}
          >
            {createMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Topic
          </Button>
          <Button type="button" variant="outline" asChild>
            <Link href="/topics">Cancel</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
