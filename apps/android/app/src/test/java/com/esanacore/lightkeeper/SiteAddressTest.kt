package com.esanacore.lightkeeper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The address check mirrors the iOS app's NightscoutClient.init, case for
 * case and reason for reason (NightscoutClientTests.swift).
 */
class SiteAddressTest {
    @Test
    fun testAddressIsRejectedWithAReasonForHttpAPathAQueryOrATypo() {
        val rejected =
            listOf(
                "http://ns.example.com" to "must start with https://",
                "https://ns.example.com/api/v1/entries" to "nothing after its name",
                "https://ns.example.com/nightscout/" to "nothing after its name",
                "https://ns.example.com/?token=abc123" to "no ?, # or login",
                "https://ns.example.com#top" to "no ?, # or login",
                "https://me:pw@ns.example.com" to "no ?, # or login",
                "htps://ns.example.com" to "must start with https://",
                "https//ns.example.com" to "full address",
                "https:/ns.example.com" to "full address",
                "ns.example.com" to "full address",
                "" to "full address",
                "https://ns,example.com" to "Check it for typos",
                "https://ns..example.com" to "Check it for typos",
                "https://ns_example.com" to "Check it for typos",
                "https://-ns.example.com" to "Check it for typos",
                "https://ns.example.com " to "space",
                "https://ns example.com" to "space",
            )
        for ((address, expected) in rejected) {
            val why = SiteAddress.problem(address)
            assertNotNull(address, why)
            assertTrue("$address: $why", why!!.contains(expected))
        }
    }

    @Test
    fun testTheReasonsAreTheIosWordsExactly() {
        assertEquals(SiteAddress.SPACE, SiteAddress.problem("https://a b"))
        assertEquals(
            "Enter the full address, starting with https://, like https://my-nightscout.example",
            SiteAddress.problem("ns.example.com"),
        )
        assertEquals(
            "The address must start with https://, so glucose data and the token are never sent " +
                "in the clear.",
            SiteAddress.problem("http://ns.example.com"),
        )
        assertEquals(
            "Enter just the site, with no ?, # or login in the address.",
            SiteAddress.problem("https://ns.example.com?x=1"),
        )
        assertEquals(
            "Enter just the site, with nothing after its name, like https://my-nightscout.example",
            SiteAddress.problem("https://ns.example.com/x"),
        )
        assertEquals(
            "The site name can only have letters, digits, hyphens, and single dots between its " +
                "parts. Check it for typos.",
            SiteAddress.problem("https://ns_x.example"),
        )
        assertEquals("The address has a space in it. Remove the space.", SiteAddress.SPACE)
    }

    @Test
    fun testJustTheSiteIsAccepted() {
        for (address in
            listOf(
                "https://ns.example.com",
                "https://ns.example.com/",
                "HTTPS://NS.Example.COM",
                "https://ns.example.com:8443",
                "https://my-ns.herokuapp.com",
                "https://ns.example.com.",
                "https://[::1]",
                "https://[::1]:8443",
                "https://localhost",
            )) {
            assertNull(address, SiteAddress.problem(address))
        }
    }

    @Test
    fun testAnEmptyQueryFragmentOrLoginStillCounts() {
        // Present but empty is still present, as Foundation reads it.
        assertEquals(SiteAddress.NO_EXTRAS, SiteAddress.problem("https://ns.example.com?"))
        assertEquals(SiteAddress.NO_EXTRAS, SiteAddress.problem("https://ns.example.com#"))
        assertEquals(SiteAddress.NO_EXTRAS, SiteAddress.problem("https://@ns.example.com"))
    }

    @Test
    fun testOddPortsAndHostsAreRefused() {
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://ns.example.com:abc"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://ns.example.com:70000"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://ns.example.com:123456"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://::1"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://[::1"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://[::1]x"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https:ns.example.com"))
        assertEquals(SiteAddress.FULL_ADDRESS, SiteAddress.problem("https://ns.example.com/%"))
        // Not ASCII, or percent-encoded: refused rather than guessed at.
        assertEquals(SiteAddress.SITE_NAME, SiteAddress.problem("https://bücher.example"))
        assertEquals(SiteAddress.SITE_NAME, SiteAddress.problem("https://ns%41.example"))
    }

    @Test
    fun testAnEmptyPortIsNoPort() {
        val site = SiteAddress.parse("https://ns.example.com:")!!
        assertEquals("https://ns.example.com/api/v1/entries/sgv.json?count=12", site.entriesUrl(12))
    }

    @Test
    fun testTheEntriesUrlIsTheSiteAndTheEndpointOnly() {
        assertEquals(
            "https://ns.example.com/api/v1/entries/sgv.json?count=12",
            SiteAddress.parse("https://ns.example.com")!!.entriesUrl(12),
        )
        assertEquals(
            "https://ns.example.com/api/v1/entries/sgv.json?count=5",
            SiteAddress.parse("https://ns.example.com/")!!.entriesUrl(5),
        )
        assertEquals(
            "https://NS.Example.COM:8443/api/v1/entries/sgv.json?count=12",
            SiteAddress.parse("HTTPS://NS.Example.COM:8443")!!.entriesUrl(12),
        )
        assertEquals(
            "https://[::1]:8443/api/v1/entries/sgv.json?count=1",
            SiteAddress.parse("https://[::1]:8443")!!.entriesUrl(1),
        )
    }

    @Test
    fun testCheckSaysUsableOrWhy() {
        assertTrue(SiteAddress.check("https://ns.example.com") is SiteAddress.Check.Usable)
        assertEquals(
            SiteAddress.Check.Unusable(SiteAddress.HTTPS_ONLY),
            SiteAddress.check("http://ns.example.com"),
        )
        assertNull(SiteAddress.parse("http://ns.example.com"))
        val site = SiteAddress.parse("https://ns.example.com")
        assertEquals("https://ns.example.com", site.toString())
    }

    @Test
    fun testSiteNames() {
        assertTrue(SiteAddress.isSiteName("ns.example.com"))
        assertTrue(SiteAddress.isSiteName("localhost"))
        assertTrue(SiteAddress.isSiteName("::1"))
        assertTrue(SiteAddress.isSiteName("[::1]"))
        assertTrue(SiteAddress.isSiteName("ns.example.com."))
        assertTrue(SiteAddress.isSiteName("a".repeat(63) + ".example"))
        assertFalse(SiteAddress.isSiteName("."))
        assertFalse(SiteAddress.isSiteName(""))
        assertFalse(SiteAddress.isSiteName("ns-.example.com"))
        assertFalse(SiteAddress.isSiteName("a".repeat(64) + ".example"))
        assertFalse(SiteAddress.isSiteName("ns%20x.example"))
        assertFalse(SiteAddress.isSiteName("bücher.example"))
        assertFalse(SiteAddress.isSiteName("[::g]"))
    }
}
