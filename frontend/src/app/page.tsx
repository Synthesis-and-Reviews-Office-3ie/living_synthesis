import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Sparkles, Zap, Shield, Clock } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Header */}
      <header className="container mx-auto flex items-center justify-between py-6 px-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-8 w-8 text-primary" />
          <span className="font-bold text-xl">Living Synthesis</span>
        </div>
        <div className="flex items-center gap-4">
          <Button variant="ghost" asChild>
            <Link href="/login">Log in</Link>
          </Button>
          <Button asChild>
            <Link href="/signup">Get Started</Link>
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-24 text-center">
        <h1 className="text-5xl font-bold tracking-tight mb-6">
          AI-Powered Evidence Synthesis
          <br />
          <span className="text-primary">Delivered Weekly</span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          Stay on top of the latest research with personalized newsletters curated by AI.
          Never miss important papers in your field again.
        </p>
        <div className="flex gap-4 justify-center">
          <Button size="lg" className="gap-2" asChild>
            <Link href="/signup">
              <Sparkles className="h-5 w-5" />
              Start Free Trial
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="#features">Learn More</Link>
          </Button>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="container mx-auto px-4 py-24">
        <h2 className="text-3xl font-bold text-center mb-12">
          Why Living Synthesis?
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          <div className="p-6 rounded-lg border bg-card">
            <Zap className="h-10 w-10 text-primary mb-4" />
            <h3 className="font-semibold text-lg mb-2">AI-Curated</h3>
            <p className="text-muted-foreground">
              Our AI reads and summarizes papers so you don&apos;t have to. 
              Get the key insights in seconds.
            </p>
          </div>
          <div className="p-6 rounded-lg border bg-card">
            <Clock className="h-10 w-10 text-primary mb-4" />
            <h3 className="font-semibold text-lg mb-2">Weekly Digests</h3>
            <p className="text-muted-foreground">
              Receive personalized newsletters on your schedule.
              Daily or weekly, you choose.
            </p>
          </div>
          <div className="p-6 rounded-lg border bg-card">
            <Shield className="h-10 w-10 text-primary mb-4" />
            <h3 className="font-semibold text-lg mb-2">Human in the Loop</h3>
            <p className="text-muted-foreground">
              Review and curate papers before they go out.
              Maintain quality control over your newsletters.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="container mx-auto px-4 py-24">
        <h2 className="text-3xl font-bold text-center mb-12">Simple Pricing</h2>
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {/* Free */}
          <div className="p-6 rounded-lg border bg-card">
            <h3 className="font-semibold text-lg mb-2">Free</h3>
            <p className="text-3xl font-bold mb-4">$0<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
            <ul className="space-y-2 text-sm text-muted-foreground mb-6">
              <li>✓ 1 topic</li>
              <li>✓ Weekly digest</li>
              <li>✓ Last 4 newsletters</li>
            </ul>
            <Button variant="outline" className="w-full" asChild>
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
          
          {/* Pro */}
          <div className="p-6 rounded-lg border-2 border-primary bg-card relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-xs px-3 py-1 rounded-full">
              Popular
            </div>
            <h3 className="font-semibold text-lg mb-2">Pro</h3>
            <p className="text-3xl font-bold mb-4">$29<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
            <ul className="space-y-2 text-sm text-muted-foreground mb-6">
              <li>✓ 3 topics</li>
              <li>✓ Daily or weekly</li>
              <li>✓ Full archive</li>
              <li>✓ API access</li>
            </ul>
            <Button className="w-full" asChild>
              <Link href="/signup?plan=pro">Start Free Trial</Link>
            </Button>
          </div>
          
          {/* Team */}
          <div className="p-6 rounded-lg border bg-card">
            <h3 className="font-semibold text-lg mb-2">Team</h3>
            <p className="text-3xl font-bold mb-4">$99<span className="text-sm font-normal text-muted-foreground">/mo</span></p>
            <ul className="space-y-2 text-sm text-muted-foreground mb-6">
              <li>✓ 10 topics</li>
              <li>✓ Team collaboration</li>
              <li>✓ Custom branding</li>
              <li>✓ Priority support</li>
            </ul>
            <Button variant="outline" className="w-full" asChild>
              <Link href="/signup?plan=team">Contact Sales</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>&copy; 2025 Living Synthesis. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
