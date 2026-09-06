import { Hero } from "./components/Hero";
import { PipelineSection } from "./components/PipelineSection";
import { FeatureGrid } from "./components/FeatureGrid";
import { ReportShowcase } from "./components/ReportShowcase";
import { SiteFooter } from "./components/SiteFooter";

// 宣传页:未登录访问 / 的单页滚动叙事
export function LandingPage() {
  return (
    <div>
      <Hero />
      <PipelineSection />
      <FeatureGrid />
      <ReportShowcase />
      <SiteFooter />
    </div>
  );
}
