package com.esanacore.lightkeeper

import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLConnection
import java.security.cert.Certificate
import javax.net.ssl.HttpsURLConnection
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * The request the app makes, checked without a network: the token travels in
 * the api-secret header and never in the URL (ADR-0009), redirects are never
 * followed, timeouts are set, every connection is closed, and no failure's
 * message carries the token.
 */
class NightscoutClientTest {
    private val site = SiteAddress.parse("https://ns.example.com")!!
    private val token = "lightkeeper-0123456789abcdef"

    /** A fake HTTPS connection that records the request and plays back one answer. */
    private class FakeHttps(
        url: String,
        private val status: Int = 200,
        private val body: ByteArray = "[]".toByteArray(),
        private val failOnStatus: Boolean = false,
        private val failOnRead: Boolean = false,
    ) : HttpsURLConnection(URI(url).toURL()) {
        var disconnected = false
        var bodyRead = false

        override fun getResponseCode(): Int {
            if (failOnStatus) throw IOException("connect timed out")
            return status
        }

        override fun getInputStream(): InputStream {
            bodyRead = true
            if (failOnRead) throw IOException("connection reset")
            return ByteArrayInputStream(body)
        }

        override fun connect() = Unit

        override fun disconnect() {
            disconnected = true
        }

        override fun usingProxy() = false

        override fun getCipherSuite() = "TLS_AES_128_GCM_SHA256"

        override fun getLocalCertificates(): Array<Certificate>? = null

        override fun getServerCertificates(): Array<Certificate> = emptyArray()
    }

    private val opened = mutableListOf<String>()

    private fun client(token: String?, connection: (String) -> URLConnection) =
        NightscoutClient(site, token) { url ->
            opened += url
            connection(url)
        }

    private fun failureOf(block: () -> Unit): NightscoutClient.FetchException {
        try {
            block()
        } catch (failed: NightscoutClient.FetchException) {
            assertFalse("the token leaked into the message", failed.message!!.contains(token))
            assertFalse("the address leaked into the message", failed.message!!.contains("example"))
            return failed
        }
        fail("the fetch did not fail")
        throw AssertionError()
    }

    @Test
    fun testTheTokenTravelsInTheHeaderNeverTheUrl() {
        var connection: FakeHttps? = null
        val body = client(token) { url -> FakeHttps(url).also { connection = it } }.fetchEntries()
        val sent = connection!!
        assertArrayEquals("[]".toByteArray(), body)
        assertEquals(listOf("https://ns.example.com/api/v1/entries/sgv.json?count=12"), opened)
        assertFalse(opened.single().contains(token))
        assertEquals(token, sent.getRequestProperty("api-secret"))
        assertEquals(NightscoutClient.TOKEN_HEADER, "api-secret")
    }

    @Test
    fun testTheRequestIsAnUncachedGetWithTimeoutsAndNoRedirects() {
        var connection: FakeHttps? = null
        client(token) { url -> FakeHttps(url).also { connection = it } }.fetchEntries(count = 5)
        val sent = connection!!
        assertEquals("GET", sent.requestMethod)
        assertEquals("application/json", sent.getRequestProperty("Accept"))
        assertFalse(sent.instanceFollowRedirects)
        assertFalse(sent.useCaches)
        assertEquals(10_000, sent.connectTimeout)
        assertEquals(10_000, sent.readTimeout)
        assertEquals("https://ns.example.com/api/v1/entries/sgv.json?count=5", opened.single())
        assertTrue(sent.disconnected)
    }

    @Test
    fun testNoTokenMeansNoHeader() {
        for (missing in listOf(null, "")) {
            var connection: FakeHttps? = null
            val nightscout = client(missing) { url -> FakeHttps(url).also { connection = it } }
            nightscout.fetchEntries()
            assertNull(connection!!.getRequestProperty("api-secret"))
            assertFalse(nightscout.sendsToken)
        }
    }

    @Test
    fun testARedirectIsRefusedAsAFailedFetch() {
        for (status in listOf(301, 302, 303, 307, 308)) {
            var connection: FakeHttps? = null
            val failed =
                failureOf {
                    client(token) { url -> FakeHttps(url, status).also { connection = it } }
                        .fetchEntries()
                }
            assertEquals(NightscoutClient.Failure.REDIRECTED, failed.failure)
            assertFalse("a redirect's body is never read", connection!!.bodyRead)
            assertTrue(connection!!.disconnected)
        }
    }

    @Test
    fun testHttpStatusesMeanWhatTheyMeanOnIos() {
        val withToken = client(token) { FakeHttps(it) }
        val without = client(null) { FakeHttps(it) }
        assertNull(withToken.failureFor(200))
        assertNull(withToken.failureFor(204))
        assertEquals(NightscoutClient.Failure.TOKEN_REJECTED, withToken.failureFor(401))
        assertEquals(NightscoutClient.Failure.TOKEN_REJECTED, withToken.failureFor(403))
        assertEquals(NightscoutClient.Failure.NEEDS_TOKEN, without.failureFor(401))
        assertEquals(NightscoutClient.Failure.NEEDS_TOKEN, without.failureFor(403))
        assertEquals(NightscoutClient.Failure.UNREACHABLE, withToken.failureFor(500))
        assertEquals(NightscoutClient.Failure.UNREACHABLE, withToken.failureFor(503))
        assertEquals(NightscoutClient.Failure.NOT_NIGHTSCOUT, withToken.failureFor(404))
        assertEquals(NightscoutClient.Failure.NOT_NIGHTSCOUT, withToken.failureFor(-1))
        assertEquals(NightscoutClient.Failure.NOT_NIGHTSCOUT, withToken.failureFor(199))
    }

    @Test
    fun testAnErrorStatusIsAFailedFetchAndClosesTheConnection() {
        var connection: FakeHttps? = null
        val failed =
            failureOf {
                client(token) { url -> FakeHttps(url, 401).also { connection = it } }.fetchEntries()
            }
        assertEquals(NightscoutClient.Failure.TOKEN_REJECTED, failed.failure)
        assertTrue(connection!!.disconnected)
    }

    @Test
    fun testTransportFailuresAreUnreachable() {
        val unreachable = NightscoutClient.Failure.UNREACHABLE
        val noAnswer = client(token) { FakeHttps(it, failOnStatus = true) }
        assertEquals(unreachable, failureOf { noAnswer.fetchEntries() }.failure)
        val cutOff = client(token) { FakeHttps(it, failOnRead = true) }
        assertEquals(unreachable, failureOf { cutOff.fetchEntries() }.failure)
        val noRoute = client(token) { throw IOException("no route to host") }
        assertEquals(unreachable, failureOf { noRoute.fetchEntries() }.failure)
    }

    @Test
    fun testAnOversizedBodyIsRefused() {
        val huge = ByteArray(NightscoutClient.MAX_RESPONSE_BYTES + 1) { ' '.code.toByte() }
        val failed = failureOf { client(token) { FakeHttps(it, body = huge) }.fetchEntries() }
        assertEquals(NightscoutClient.Failure.NOT_NIGHTSCOUT, failed.failure)
        val largest = ByteArray(NightscoutClient.MAX_RESPONSE_BYTES) { ' '.code.toByte() }
        assertEquals(
            NightscoutClient.MAX_RESPONSE_BYTES,
            client(token) { FakeHttps(it, body = largest) }.fetchEntries().size,
        )
    }

    @Test
    fun testAConnectionThatIsNotHttpsSendsNothing() {
        var plain: HttpURLConnection? = null
        val failed =
            failureOf {
                client(token) { url ->
                        object : HttpURLConnection(URI(url).toURL()) {
                            override fun connect() = fail("connected")
                            override fun disconnect() = Unit
                            override fun usingProxy() = false
                        }
                            .also { plain = it }
                    }
                    .fetchEntries()
            }
        assertEquals(NightscoutClient.Failure.NOT_NIGHTSCOUT, failed.failure)
        assertNull(plain!!.getRequestProperty("api-secret"))
    }

    @Test
    fun testTheCountIsBounded() {
        val nightscout = client(token) { FakeHttps(it) }
        for (count in listOf(0, 289)) {
            try {
                nightscout.fetchEntries(count)
                fail("count $count was accepted")
            } catch (_: IllegalArgumentException) {
                // Expected: 1 to 288, a day of 5-minute readings.
            }
        }
        assertTrue(opened.isEmpty())
    }
}
