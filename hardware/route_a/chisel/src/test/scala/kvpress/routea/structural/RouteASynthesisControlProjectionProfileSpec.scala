package kvpress.routea.structural

import kvpress.routea.params.{RouteAAnchorWidths, RouteASynthesisControlProjectionProfile}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

/** Static profile guard; it deliberately does not emit the large anchor DUT. */
final class RouteASynthesisControlProjectionProfileSpec extends AnyFlatSpec with Matchers {
  behavior of "qwen3_8b_32k_s1_control_projection_v1"

  it should "name one complete non-test-only paired control profile" in {
    val p = RouteASynthesisControlProjectionProfile.parameters
    RouteASynthesisControlProjectionProfile.profileId shouldBe "qwen3_8b_32k_s1_control_projection_v1"
    p.pendingDescriptorRefWidth shouldBe RouteAAnchorWidths.PageIdWidth
    p.pendingValidityWidth shouldBe RouteAAnchorWidths.PageGenerationWidth
    p.candidateOrdinalWidth shouldBe 7
    p.candidateIdWidth shouldBe 4
    p.r2CandidateSlotsPerClass shouldBe 2
    p.sourceDeliveryOpaqueWidth shouldBe 4
    p.transactionGroupTagWidth shouldBe 8
    p.p3StageGenerationWidth shouldBe 8
    p.sourceGenerationWidth shouldBe 8
    p.coreMemoryFragmentCountWidth shouldBe 10
    p.coreMemoryFragmentIndexWidth shouldBe 9
    p.r5AllocatorEntries shouldBe 146880
    p.r5StreamSlots shouldBe 288
    p.r6.attentionTrackerEntries shouldBe 4
  }
}
