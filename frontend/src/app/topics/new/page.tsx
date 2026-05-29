"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { topicsApi, aiApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Loader2, Sparkles, Check, X, Search, RefreshCw } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

type Step = "describe" | "review" | "test";

const SOURCES = [
  { key: "openalex", label: "OpenAlex", description: "Comprehensive academic database" },
  { key: "pubmed", label: "PubMed", description: "Biomedical literature" },
  { key: "arxiv", label: "arXiv", description: "Preprints (CS, physics, math, biology)" },
  { key: "google_scholar", label: "Google Scholar", description: "Web scraping (may be rate-limited)" },
];

export default function NewTopicPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  
  const [step, setStep] = useState<Step>("describe");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [queries, setQueries] = useState<Record<string, string>>({});
  const [explanation, setExplanation] = useState("");
  const [testResults, setTestResults] = useState<Record<string, any>>({});
  const [testingSource, setTestingSource] = useState<string | null>(null);

  // Generate queries using LLM
  const generateMutation = useMutation({
    mutationFn: async () => {
      const response = await aiApi.generateQueries(description);
      return response.data;
    },
    onSuccess: (data) => {
      setQueries(data.queries || {});
      setExplanation(data.explanation || "");
      setStep("review");
      toast.success("Queries generated! Review and adjust if needed.");
    },
    onError: (error: any) => {
      console.error("Generate queries error:", error);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      
      if (status === 401) {
        toast.error("Please log in again to use this feature");
      } else if (status === 404) {
        toast.error("API endpoint not found. Please check the backend is running.");
      } else {
        toast.error(detail || "Failed to generate queries. Please try again.");
      }
    },
  });

  // Test a query
  const testQueryMutation = useMutation({
    mutationFn: async ({ query, source }: { query: string; source: string }) => {
      setTestingSource(source);
      const response = await aiApi.testQuery(query, source, 5);
      return { source, data: response.data };
    },
    onSuccess: ({ source, data }) => {
      setTestResults((prev) => ({ ...prev, [source]: data }));
      setTestingSource(null);
      if (data.error) {
        toast.error(`${source}: ${data.error}`);
      } else {
        toast.success(`${source}: Found ${data.result_count} papers`);
      }
    },
    onError: (error: any) => {
      setTestingSource(null);
      toast.error("Failed to test query");
    },
  });

  // Create topic
  const createMutation = useMutation({
    mutationFn: async () => {
      const response = await topicsApi.create({
        name,
        description: description || undefined,
        queries: Object.fromEntries(
          Object.entries(queries).filter(([_, v]) => v.trim())
        ),
        frequency: "weekly",
      });
      return response.data;
    },
    onSuccess: (data) => {
      toast.success("Topic created! Redirecting to your new topic...");
      // Invalidate topics cache so the list refreshes
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      // Redirect to the newly created topic's detail page
      router.push(`/topics/${data.id}`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create topic");
    },
  });

  const handleGenerate = () => {
    if (!description.trim() || description.length < 20) {
      toast.error("Please provide a more detailed description (at least 20 characters)");
      return;
    }
    generateMutation.mutate();
  };

  const handleTestAll = () => {
    Object.entries(queries).forEach(([source, query]) => {
      if (query.trim()) {
        testQueryMutation.mutate({ query, source });
      }
    });
  };

  const handleCreate = () => {
    const filledQueries = Object.values(queries).filter((q) => q.trim());
    if (filledQueries.length === 0) {
      toast.error("Please have at least one search query");
      return;
    }
    if (!name.trim()) {
      toast.error("Please enter a topic name");
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <Link href="/topics">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Create Topic</h1>
          <p className="text-muted-foreground">
            Describe your research interest and let AI generate search queries
          </p>
        </div>
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-2">
        <Badge variant={step === "describe" ? "default" : "secondary"}>
          1. Describe
        </Badge>
        <span className="text-muted-foreground">→</span>
        <Badge variant={step === "review" ? "default" : "secondary"}>
          2. Review Queries
        </Badge>
        <span className="text-muted-foreground">→</span>
        <Badge variant={step === "test" ? "default" : "secondary"}>
          3. Test & Create
        </Badge>
      </div>

      {/* Step 1: Describe */}
      {step === "describe" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Describe Your Research Interest
            </CardTitle>
            <CardDescription>
              Tell us what kind of papers you want to find. Be specific about your topic,
              methodology, or field of interest.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Topic Name *</Label>
              <Input
                id="name"
                placeholder="e.g., AI in Systematic Reviews"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Research Description *</Label>
              <Textarea
                id="description"
                placeholder="Describe what you're looking for. For example: 'I want to find papers about using large language models (LLMs) like GPT-4 or Claude to assist with systematic reviews, evidence synthesis, or meta-analyses. I'm interested in automation of screening, data extraction, and quality assessment.'"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={5}
              />
              <p className="text-xs text-muted-foreground">
                {description.length}/20 characters minimum
              </p>
            </div>
            <Button 
              onClick={handleGenerate} 
              disabled={generateMutation.isPending || description.length < 20}
              className="w-full"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating Queries...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate Search Queries
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Review Queries */}
      {step === "review" && (
        <>
          {explanation && (
            <Card className="bg-muted/50">
              <CardContent className="pt-4">
                <p className="text-sm text-muted-foreground">
                  <strong>Search Strategy:</strong> {explanation}
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Review Generated Queries</CardTitle>
              <CardDescription>
                Review and edit the generated queries for each database. You can modify them to better match your needs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {SOURCES.map((source) => (
                <div key={source.key} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor={source.key}>
                      {source.label}
                      <span className="text-xs text-muted-foreground ml-2">
                        ({source.description})
                      </span>
                    </Label>
                  </div>
                  <Textarea
                    id={source.key}
                    value={queries[source.key] || ""}
                    onChange={(e) =>
                      setQueries((prev) => ({ ...prev, [source.key]: e.target.value }))
                    }
                    rows={2}
                    className="font-mono text-sm"
                  />
                </div>
              ))}

              <div className="flex gap-4">
                <Button variant="outline" onClick={() => setStep("describe")}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back
                </Button>
                <Button variant="outline" onClick={handleGenerate} disabled={generateMutation.isPending}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Regenerate
                </Button>
                <Button onClick={() => setStep("test")} className="flex-1">
                  Continue to Test
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Step 3: Test & Create */}
      {step === "test" && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Test Your Queries</CardTitle>
              <CardDescription>
                Test each query to see sample results before creating the topic.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {SOURCES.map((source) => {
                const query = queries[source.key];
                const result = testResults[source.key];
                const isTesting = testingSource === source.key;

                if (!query?.trim()) return null;

                return (
                  <div key={source.key} className="border rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium">{source.label}</h4>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => testQueryMutation.mutate({ query, source: source.key })}
                        disabled={isTesting}
                      >
                        {isTesting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <Search className="h-4 w-4 mr-1" />
                            Test
                          </>
                        )}
                      </Button>
                    </div>
                    <code className="text-xs bg-muted px-2 py-1 rounded block whitespace-pre-wrap">
                      {query}
                    </code>

                    {result && (
                      <div className="mt-2">
                        {result.error ? (
                          <p className="text-sm text-red-500 flex items-center gap-1">
                            <X className="h-4 w-4" />
                            Error: {result.error}
                          </p>
                        ) : (
                          <>
                            <p className="text-sm text-green-600 flex items-center gap-1 mb-2">
                              <Check className="h-4 w-4" />
                              Found {result.result_count} papers
                            </p>
                            {result.sample_papers?.length > 0 && (
                              <div className="space-y-2">
                                {result.sample_papers.slice(0, 3).map((paper: any, i: number) => (
                                  <div key={i} className="text-xs bg-muted/50 p-2 rounded">
                                    <p className="font-medium line-clamp-1">{paper.title}</p>
                                    <p className="text-muted-foreground">
                                      {paper.authors?.join(", ")}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="flex gap-4 pt-4">
                <Button variant="outline" onClick={() => setStep("review")}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Edit
                </Button>
                <Button
                  variant="outline"
                  onClick={handleTestAll}
                  disabled={testQueryMutation.isPending}
                >
                  Test All Queries
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createMutation.isPending}
                  className="flex-1"
                >
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Check className="mr-2 h-4 w-4" />
                      Create Topic
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
