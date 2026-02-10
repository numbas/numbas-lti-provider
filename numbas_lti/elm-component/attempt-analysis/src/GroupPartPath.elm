module GroupPartPath exposing
  ( GroupPartPath
  , toString
  , fromString
  )

import Parser as P exposing (Parser, (|.), (|=))
import PartPath exposing (PartPath)
import Tuple exposing (pair)
import Util exposing (alpha)

type alias GroupPartPath = (Int,PartPath)

toString : GroupPartPath -> String
toString (gn,path) = (String.fromInt gn)++(PartPath.toString path)

parse_group_path : Parser GroupPartPath
parse_group_path =
  P.succeed pair
  |= (P.int)
  |= (PartPath.parse_path)

fromString : String -> Maybe GroupPartPath
fromString = P.run parse_group_path >> Result.toMaybe
