//
// Time Ordered Astrophysics Scalable Tools (TOAST)
//
// Copyright (c) 2015-2017, The Regents of the University of California
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice,
// this list of conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice,
// this list of conditions and the following disclaimer in the documentation
// and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//


#ifndef timer_hpp_
#define timer_hpp_

//----------------------------------------------------------------------------//

#include "base_timer.hpp"

#include <cereal/types/polymorphic.hpp>

namespace toast
{
namespace util
{

//============================================================================//
// Main timer class
//============================================================================//

class timer : public details::base_timer
{
public:
    typedef base_timer                      base_type;
    typedef timer                           this_type;
    typedef std::string                     string_t;

public:
    timer(const string_t& _begin = "[ ",
          const string_t& _close = " ]",
          bool _use_static_width = true,
          uint16_t prec = default_precision);
    timer(const string_t& _begin,
          const string_t& _close,
          const string_t& _fmt,
          bool _use_static_width = false,
          uint16_t prec = default_precision);
    virtual ~timer();

public:
    static string_t default_format;
    static uint16_t default_precision;
    static void propose_output_width(uint64_t);

public:
    timer& stop_and_return() { this->stop(); return *this; }
    string_t begin() const { return m_begin; }
    string_t close() const { return m_close; }

protected:
    virtual void compose() final;

protected:
    bool     m_use_static_width;
    string_t m_begin;
    string_t m_close;

private:
    static thread_local uint64_t f_output_width;

public:
    template <typename Archive> void
    serialize(Archive& ar, const unsigned int version)
    {
        details::base_timer::serialize(ar, version);
    }

};

//----------------------------------------------------------------------------//

} // namespace util

} // namespace toast

//----------------------------------------------------------------------------//

#endif // timer_hpp_
